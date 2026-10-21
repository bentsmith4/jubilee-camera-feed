"""Offline grid failure provenance and fail-closed publication regressions."""
import contextlib
import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from model_data import ingest_ngofs2_shoreline_grid as grid
from model_data import validate_ngofs2_availability as availability

CYCLE = datetime(2026, 10, 17, 15, tzinfo=timezone.utc)
URL = grid.regulargrid_url(CYCLE, "nowcast", 3)


class GridFailureTests(unittest.TestCase):
    def test_narrow_remote_retrieval_signatures(self):
        for stage in ("reference_open", "reference_read", "slice_open", "slice_read"):
            for exc in (OSError(-90, "NetCDF: file not found", URL),
                        RuntimeError("NetCDF: file not found"),
                        OSError(-70, "NetCDF: DAP server error", URL),
                        RuntimeError("NetCDF: DAP server error"),
                        HTTPError(URL, 404, "Not Found", {}, None),
                        HTTPError(URL, 503, "Service Unavailable", {}, None)):
                with self.subTest(stage=stage, exception=exc):
                    attempt = grid.grid_failure(exc, URL, stage, "nowcast", 3)
                    self.assertEqual(attempt["error"], str(exc))
                    self.assertEqual(attempt["failure_kind"], "retrieval")
                    self.assertTrue(availability.grid_retrieval_failure(attempt))

    def test_data_errors_and_unverified_remote_errors_remain_fatal(self):
        failures = (
            ValueError("HTTP 503 Service Unavailable while parsing invalid schema"),
            ValueError("NetCDF: DAP server error"),
            KeyError("time"), IndexError("dimension mismatch"),
            RuntimeError("NetCDF: DAP failure"),
            RuntimeError("NetCDF: libcurl failure"),
            RuntimeError("NetCDF: Variable has no data"),
            RuntimeError("NetCDF: Malformed or inaccessible DAP2 DDS or DAP4 DMR response"),
            OSError("NetCDF: I/O failure"), OSError(-72, "NetCDF: DAP server error"),
            OSError(-90, "NetCDF: file not found", "local.nc"),
            OSError(-90, "NetCDF: file not found", URL.replace("n003", "n004")),
            HTTPError(URL, 401, "Unauthorized", {}, None),
        )
        for exc in failures:
            with self.subTest(exception=exc):
                attempt = grid.grid_failure(exc, URL, "slice_read", "nowcast", 3)
                self.assertEqual(attempt["failure_kind"], "extraction_or_data")
                self.assertFalse(availability.grid_retrieval_failure(attempt))
        good = grid.grid_failure(RuntimeError("NetCDF: DAP server error"), URL,
                                 "slice_read", "nowcast", 3)
        for changes in ({"stage": "csv_write"}, {"stage": "slice_close"},
                        {"source_url": "local.nc"}, {"source_url": "https://example.com/file.nc"},
                        {"error": good["error"] + "; invalid schema"}):
            self.assertFalse(availability.grid_retrieval_failure({**good, **changes}))

    def test_structured_contract_never_falls_back_to_legacy_text(self):
        good = grid.grid_failure(RuntimeError("NetCDF: DAP server error"), URL,
                                 "slice_read", "nowcast", 3)
        base = {"failure_contract": availability.GRID_FAILURE_CONTRACT,
                "error_type": "GridRetrievalError", "retrieval_attempts": [good],
                "error": "HTTP 503 Service Unavailable"}
        self.assertTrue(availability.retrieval_outage(base))
        for changes in ({"retrieval_attempts": []}, {"retrieval_attempts": None},
                        {"retrieval_attempts": [good, {"error_type": "ValueError"}]},
                        {"retrieval_attempts": ["bad"]}, {"error_type": "ValueError"},
                        {"error_type": "RuntimeError"}, {"failure_contract": "future_unknown"}):
            self.assertFalse(availability.retrieval_outage({**base, **changes}))
        self.assertFalse(availability.retrieval_outage({
            "error_type": "GridRetrievalError", "retrieval_attempts": [good]}))

    def collect(self, root, outcomes, *, reference_error=None, close_error=None):
        """Use real collector orchestration without any network or model call."""
        datasets = []
        def dataset(url, mode):
            if not datasets:
                obj = Mock()
                datasets.append(obj)
                return obj
            lead = int(url.rsplit(".", 2)[-2][1:])
            stage, outcome = outcomes.get(lead, ("read", None))
            if stage == "open":
                raise outcome
            obj = Mock(outcome=outcome)
            if close_error is not None:
                obj.close.side_effect = close_error
            datasets.append(obj)
            return obj
        def extract(ds, url, cycle, cast, lead, nodes, retrieved):
            if isinstance(ds.outcome, Exception):
                raise ds.outcome
            if ds.outcome == "empty":
                return CYCLE, [], [], []
            return CYCLE, [{"lead_hour": lead}], [{"variable_or_evidence_type": "test",
                                                   "production_weight": 0.0}], []
        with patch.object(grid, "HERE", root), patch.object(grid, "Dataset", side_effect=dataset), \
             patch.object(grid, "load_targets", return_value=[]), \
             patch.object(grid, "select_nodes", side_effect=reference_error, return_value=[]), \
             patch.object(grid, "extract_one_file", side_effect=extract), \
             patch.object(grid, "cycle_candidates", return_value=[CYCLE]), \
             patch("sys.argv", ["grid", "--casts", "nowcast"]), contextlib.redirect_stdout(io.StringIO()):
            try:
                grid.main()
            except SystemExit as exc:
                self.assertEqual(exc.code, 1)
        for ds in datasets:
            ds.close.assert_called_once()
        return json.loads((root / "ngofs2_shoreline_grid_manifest.json").read_text())

    def prepare(self, root):
        for product, csvs in availability.PRODUCTS.items():
            (root / f"{product}_manifest.json").write_text('{"status":"complete"}')
            for name in csvs:
                (root / name).write_text("old rows")
        archive = root / "public_archive" / "old.gz"
        archive.parent.mkdir()
        archive.write_bytes(b"immutable archive")
        return archive

    def test_six_slice_incident_becomes_unavailable_and_clears_only_grid(self):
        # Run 39082788138: two missing slices, four DAP failures, reference opened.
        # The old aggregate did not identify open/read stage; these are injected boundaries.
        outcomes = {lead: ("open", OSError(-90, "NetCDF: file not found",
                                          grid.regulargrid_url(CYCLE, "nowcast", lead)))
                    for lead in (1, 2)}
        outcomes[3] = ("read", RuntimeError("NetCDF: DAP server error"))
        outcomes.update({lead: ("open", OSError(-70, "NetCDF: DAP server error",
                                               grid.regulargrid_url(CYCLE, "nowcast", lead)))
                         for lead in (4, 5, 6)})
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = self.prepare(root)
            manifest = self.collect(root, outcomes)
            self.assertEqual(manifest["status"], "failed")
            self.assertEqual(manifest["error_type"], "GridRetrievalError")
            self.assertEqual(len(manifest["retrieval_attempts"]), 6)
            self.assertEqual(manifest["casts"][0]["opened_slices"], [])
            self.assertEqual(manifest["retrieval_attempts"], manifest["casts"][0]["failed_slices"])
            result = availability.validate(root)
            self.assertEqual(result["ngofs2_shoreline_grid"], "unavailable")
            self.assertTrue(all(v == "complete" for k, v in result.items() if k != "ngofs2_shoreline_grid"))
            saved = json.loads((root / "ngofs2_shoreline_grid_manifest.json").read_text())
            self.assertEqual(saved["retrieval_attempts"], manifest["retrieval_attempts"])
            self.assertEqual(saved["production_action"], "NO_CURRENT_GUIDANCE")
            for name in availability.PRODUCTS["ngofs2_shoreline_grid"]:
                self.assertFalse((root / name).exists())
            self.assertEqual(archive.read_bytes(), b"immutable archive")
            self.assertEqual(list(root.rglob("*.gz")), [archive])
            self.assertEqual((root / "ngofs2_point_clear_nowcast_normalized.csv").read_text(), "old rows")

    def test_one_slice_stays_unavailable_two_retrieval_only_slices_preserve_behavior(self):
        for successes in (1, 2):
            with self.subTest(successes=successes), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                outcomes = {lead: ("read", RuntimeError("NetCDF: DAP server error"))
                            for lead in range(successes + 1, 7)}
                manifest = self.collect(root, outcomes)
                self.assertEqual(len(manifest["casts"][0]["opened_slices"]), successes)
                if successes == 1:
                    self.assertEqual(manifest["status"], "failed")
                    self.assertTrue(availability.retrieval_outage(manifest))
                else:
                    self.assertEqual(manifest["status"], "complete")
                    self.assertEqual(manifest["normalized_rows"], 2)
                    self.assertEqual(manifest["source_class"], "MODEL")
                    self.assertIn("0.0", (root / "ngofs2_shoreline_grid_normalized.csv").read_text())

    def test_parser_errors_are_fatal_even_after_two_successful_slices(self):
        for outcome in (ValueError("missing variables"), KeyError("time"),
                        IndexError("dimension mismatch"), "empty",
                        ValueError("HTTP 503 Service Unavailable; invalid schema")):
            with self.subTest(outcome=outcome), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                self.prepare(root)
                manifest = self.collect(root, {3: ("read", outcome)})
                self.assertEqual(manifest["status"], "failed")
                self.assertEqual(len(manifest["casts"][0]["opened_slices"]), 2)
                self.assertEqual(manifest["casts"][0]["failed_slices"][0]["failure_kind"], "extraction_or_data")
                self.assertFalse(availability.retrieval_outage(manifest))
                with self.assertRaisesRegex(RuntimeError, "validation or parser failure"):
                    availability.validate(root)
                self.assertEqual((root / "ngofs2_shoreline_grid_normalized.csv").read_text(), "old rows")

    def test_reference_and_close_defects_keep_their_stage_and_are_fatal(self):
        for error in (ValueError("reference missing Latitude"), KeyError("Depth")):
            with tempfile.TemporaryDirectory() as temp:
                manifest = self.collect(Path(temp), {}, reference_error=error)
                self.assertFalse(availability.retrieval_outage(manifest))
                self.assertEqual(manifest["casts"][0]["failed_slices"][0]["stage"], "reference_read")
        with tempfile.TemporaryDirectory() as temp:
            manifest = self.collect(Path(temp), {}, close_error=RuntimeError("NetCDF: DAP server error"))
            self.assertFalse(availability.retrieval_outage(manifest))

    def test_reference_lazy_server_failure_remains_retrieval_only(self):
        with tempfile.TemporaryDirectory() as temp:
            manifest = self.collect(Path(temp), {}, reference_error=RuntimeError("NetCDF: DAP server error"))
            self.assertTrue(availability.retrieval_outage(manifest))
            self.assertEqual(manifest["retrieval_attempts"][0]["stage"], "reference_read")

    def test_reference_open_records_full_attempts_and_rejects_mixed_defects(self):
        with patch.object(grid, "cycle_candidates", return_value=[CYCLE]), \
             patch.object(grid, "Dataset", side_effect=OSError(-90, "NetCDF: file not found", URL)):
            with self.assertRaises(grid.GridRetrievalError) as caught:
                grid.open_reference("nowcast", CYCLE)
        self.assertEqual(caught.exception.attempts[0]["error"], str(OSError(-90, "NetCDF: file not found", URL)))
        with patch.object(grid, "cycle_candidates", return_value=[CYCLE, CYCLE]), \
             patch.object(grid, "Dataset", side_effect=[RuntimeError("NetCDF: DAP server error"), ValueError("bad schema")]):
            attempts = []
            with self.assertRaisesRegex(ValueError, "bad schema"):
                grid.open_reference("nowcast", CYCLE, attempts)
        self.assertEqual([a["failure_kind"] for a in attempts], ["retrieval", "extraction_or_data"])


if __name__ == "__main__":
    unittest.main()
