"""Offline binding regressions; live file consistency is checked by dedicated CI.

Independent sensing producers must not be blocked by a stale forecast artifact.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "model_data/bind_current_forecast.py"
FIXTURES = ROOT / "tests/fixtures/forecast_binding"
spec = importlib.util.spec_from_file_location("binding", SCRIPT)
binding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(binding)


def encode(value):
    return (json.dumps(value, indent=2) + "\n").encode()


def snapshot():
    return {
        "snapshot_time_ct": "2026-09-27T21:56:29.128-05:00",
        "forecast_weights_changed": False,
        "probability_basis": {"probability_type": binding.PROBABILITY_TYPE,
                              "numeric_change_from_prior_snapshot": 0,
                              "reassessment_method": "Frozen heuristic; no new weights"},
        "reconciliation": {"as_of_utc": "2026-09-28T02:56:29.128+00:00",
                           "input_commit_sha": "d" * 40,
                           "alert_threshold_percent": 20, "alert_comparator": ">"},
        "known_unknowns": ["Direct bottom oxygen UNKNOWN", "Blank precipitation UNKNOWN, not zero"],
        "input_rows": [
            {"source": "bentsmith4/jubilee-camera-feed status.json, burst_status.json and vision.json",
             "camera_health": {"private_metadata_pass": 4, "expected_private_cameras": 6}},
            {"source": "NOAA NGOFS2 repository manifests", "production_weight": 0,
             "products": {"forecast": {"admitted_status": "ADMITTED_FORWARD_MODEL_GUIDANCE", "production_weight": 0},
                          "named_forecast": {"admitted_status": "UNKNOWN_UNAVAILABLE", "production_weight": 0}}},
            {"source": "USGS NWIS lower-river forcing manifest", "production_weight": 0,
             "series": [{"fresh": True, "value_status": "KNOWN_UPSTREAM_PROXY", "production_weight": 0},
                        {"fresh": False, "value_status": "UNKNOWN_STALE", "production_weight": 0}]},
            {"source": "NOAA/NWS ASOS KBFM and KMOB", "production_weight": 0,
             "parameter_admission": {station: {"wind_speed": {"value": 0, "value_status": "KNOWN"},
                                               "rain": {"value": None, "value_status": "UNKNOWN"}}
                                     for station in ("KBFM", "KMOB")}},
        ],
        "outlook": [{"date_ct": "2026-09-27", "point_clear_range_percent": "2-6", "point_clear_central_percent": 4,
                     "daphne_may_day_range_percent": "1-5", "daphne_may_day_central_percent": 3, "confidence": "low"}],
        "alert_gates": {"point_clear_over_20_percent": False, "daphne_may_day_over_20_percent": False,
                        "direct_event_evidence_present": False, "material_critical_input_fault": False,
                        "notification_suppressed": True},
        "notification_condition_met": False,
    }


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.state = snapshot()
        self.raw = encode(self.state)
        self.forecast = binding.project(self.raw)

    def test_projection_preserves_assessed_values_and_unknowns(self):
        self.assertEqual(self.forecast["outlooks"][0]["range_percent"], "2-6")
        self.assertEqual(self.forecast["outlooks"][0]["central_percent"], 4)
        self.assertEqual(self.forecast["missing_inputs"], self.state["known_unknowns"])
        self.assertEqual(self.forecast["input_snapshot_hash"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.forecast["input_commit_sha"], "d" * 40)
        self.assertEqual(self.forecast["data_coverage"]["ngofs2_products"]["named_forecast"], "UNKNOWN_UNAVAILABLE")
        self.assertEqual(self.forecast["data_coverage"]["fresh_river_series"], 1)
        self.assertEqual(self.forecast["data_coverage"]["asos_stations"], "KBFM/KMOB partial")
        self.assertFalse(self.forecast["notification_condition_met"])
        self.assertEqual(encode(self.state), self.raw)
        binding.check(self.raw, self.forecast)

    def test_probability_basis_rejects_invalid_shapes_and_missing_fields(self):
        for value in (None, "Frozen baseline; no numerical change", [], 0, False):
            with self.subTest(value=value):
                self.state["probability_basis"] = value
                with self.assertRaisesRegex(ValueError, "probability_basis must be an object"):
                    binding.project(encode(self.state))
        for field in snapshot()["probability_basis"]:
            self.state = snapshot()
            del self.state["probability_basis"][field]
            with self.assertRaisesRegex(ValueError, f"probability_basis.{field} is required"):
                binding.project(encode(self.state))

    def test_probability_basis_requires_numeric_zero_and_real_method(self):
        for change in (False, True, "0", None, [], 1, -1, float("nan"), float("inf")):
            with self.subTest(change=change):
                self.state["probability_basis"]["numeric_change_from_prior_snapshot"] = change
                with self.assertRaisesRegex(ValueError, "numeric_change_from_prior_snapshot"):
                    binding.project(encode(self.state))
        self.state = snapshot()
        for method in (None, "", " \t", [], {}, 42):
            with self.subTest(method=method):
                self.state["probability_basis"]["reassessment_method"] = method
                with self.assertRaisesRegex(ValueError, "reassessment_method"):
                    binding.project(encode(self.state))

    def test_new_snapshot_time_rejects_old_forecast(self):
        self.state["snapshot_time_ct"] = "2026-09-27T22:00:00-05:00"
        self.state["reconciliation"]["as_of_utc"] = "2026-09-28T03:00:00+00:00"
        with self.assertRaisesRegex(ValueError, "issue_time"):
            binding.check(encode(self.state), self.forecast)

    def test_same_timestamp_correction_rejects_old_hash(self):
        self.state["readback_correction"] = True
        with self.assertRaisesRegex(ValueError, "input_snapshot_hash"):
            binding.check(encode(self.state), self.forecast)
        # Even semantically equivalent byte changes require an exact new binding.
        with self.assertRaisesRegex(ValueError, "input_snapshot_hash"):
            binding.check(self.raw + b"\n", self.forecast)

    def test_hash_only_repair_does_not_hide_stale_missing_inputs(self):
        self.state["known_unknowns"].append("Grand Hotel biology UNKNOWN in darkness")
        raw = encode(self.state)
        self.forecast["input_snapshot_hash"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ValueError, "missing_inputs"):
            binding.check(raw, self.forecast)

    def test_input_commit_and_coverage_must_follow_snapshot(self):
        for change, field in ((lambda s: s["reconciliation"].update(input_commit_sha="e" * 40), "input_commit_sha"),
                              (lambda s: s["input_rows"][0]["camera_health"].update(private_metadata_pass=3), "data_coverage")):
            state = copy.deepcopy(self.state)
            change(state)
            with self.assertRaisesRegex(ValueError, field):
                binding.check(encode(state), self.forecast)

    def test_mutated_forecast_fields_fail_without_snapshot_change(self):
        for field, value in (("outlooks", []), ("alert_gates", {}), ("alert_comparator", ">="),
                             ("alert_threshold_percent", 21), ("forecast_weights_changed", True),
                             ("issue_time", "now"), ("extra", None)):
            with self.subTest(field=field):
                forecast = copy.deepcopy(self.forecast)
                forecast[field] = value
                with self.assertRaisesRegex(ValueError, field):
                    binding.check(self.raw, forecast)

    def test_20_is_not_over_20_and_range_upper_is_not_central(self):
        for central in (19, 20, 20.001):
            with self.subTest(central=central):
                state = copy.deepcopy(self.state)
                state["outlook"][0].update(point_clear_range_percent="15-25", point_clear_central_percent=central)
                hit = central > 20
                state["alert_gates"].update(point_clear_over_20_percent=hit, notification_suppressed=not hit)
                state["notification_condition_met"] = hit
                forecast = binding.project(encode(state))
                self.assertEqual(forecast["notification_condition_met"], hit)
                self.assertEqual(forecast["alert_comparator"], ">")

    def test_inconsistent_gate_or_notification_is_not_silently_repaired(self):
        for field in ("point_clear_over_20_percent", "notification_suppressed"):
            state = copy.deepcopy(self.state)
            state["alert_gates"][field] = not state["alert_gates"][field]
            with self.assertRaisesRegex(ValueError, "gate"):
                binding.project(encode(state))

    def test_direct_event_and_material_fault_gates_remain_separate(self):
        for field in ("direct_event_evidence_present", "material_critical_input_fault"):
            state = copy.deepcopy(self.state)
            state["alert_gates"].update({field: True, "notification_suppressed": False})
            state["notification_condition_met"] = True
            forecast = binding.project(encode(state))
            self.assertTrue(forecast["alert_gates"][field])
            self.assertFalse(forecast["alert_gates"]["point_clear_over_20_percent"])

    def test_promoted_nested_weight_or_changed_policy_is_rejected(self):
        changes = [lambda s: s["input_rows"][1]["products"]["forecast"].update(production_weight=0.1),
                   lambda s: s["reconciliation"].update(alert_comparator=">="),
                   lambda s: s.update(forecast_weights_changed=True),
                   lambda s: s["probability_basis"].update(numeric_change_from_prior_snapshot=1)]
        for change in changes:
            state = copy.deepcopy(self.state)
            change(state)
            with self.assertRaises(ValueError):
                binding.project(encode(state))

    def test_stale_weather_and_river_remain_unknown_coverage(self):
        for row in self.state["input_rows"][3]["parameter_admission"].values():
            row["wind_speed"].update(value=None, value_status="UNKNOWN_STALE")
        self.state["input_rows"][2]["series"][0].update(fresh=False, value_status="UNKNOWN_STALE")
        forecast = binding.project(encode(self.state))
        self.assertEqual(forecast["data_coverage"]["asos_stations"], "KBFM/KMOB UNKNOWN")
        self.assertEqual(forecast["data_coverage"]["fresh_river_series"], 0)
        self.assertEqual(forecast["outlooks"], self.forecast["outlooks"])

    def test_station_envelope_preserves_flat_admission_including_trace(self):
        for status, values in (("KNOWN", ("KNOWN", "KNOWN")),
                               ("PARTIAL", ("KNOWN", "UNKNOWN")),
                               ("PARTIAL_FRESH", ("KNOWN", "UNKNOWN")),
                               ("PARTIAL", ("TRACE", "UNKNOWN")),
                               ("UNKNOWN", ("UNKNOWN", "UNKNOWN"))):
            with self.subTest(status=status, values=values):
                state = snapshot()
                stations = state["input_rows"][3]["parameter_admission"]
                for params in stations.values():
                    for parameter, value_status in zip(params.values(), values):
                        parameter["value_status"] = value_status
                flat = binding.project(encode(state))
                for station, params in list(stations.items()):
                    stations[station] = {"status": status, "parameters": params}
                wrapped = binding.project(encode(state))
                self.assertEqual(flat["data_coverage"], wrapped["data_coverage"])
                self.assertEqual(flat["outlooks"], wrapped["outlooks"])

    def test_material_change_cannot_bypass_explicit_notification_gates(self):
        # Production 00:34 CT (2d9c17f) declares recovery notification without
        # any true trigger gate. Schema repair must not silently bless it.
        self.state["material_change_since_prior_snapshot"] = True
        self.state["notification_reason"] = "Material input-quality recovery"
        self.state["notification_condition_met"] = True
        self.state["alert_gates"]["notification_suppressed"] = False
        with self.assertRaisesRegex(ValueError, "Snapshot notification gates disagree"):
            binding.project(encode(self.state))

    def test_production_shaped_recovery_context_is_not_a_forecast_trigger(self):
        recovery = json.loads((FIXTURES / "recovery_no_forecast_trigger_20260928T0034.json").read_text())
        state = snapshot()
        state["material_change_since_prior_snapshot"] = recovery["material_change_since_prior_snapshot"]
        state["notification_reason"] = recovery["notification_reason"]
        state["operational_fault_assessment"] = recovery["operational_fault_assessment"]
        state["alert_gates"].update(recovery["alert_gates"])
        state["notification_condition_met"] = recovery["notification_condition_met"]

        raw = encode(state)
        forecast = binding.project(raw)
        binding.check(raw, forecast)

        self.assertFalse(forecast["notification_condition_met"])
        self.assertTrue(forecast["alert_gates"]["notification_suppressed"])
        for field in ("point_clear_over_20_percent", "daphne_may_day_over_20_percent",
                      "direct_event_evidence_present", "material_critical_input_fault"):
            self.assertFalse(forecast["alert_gates"][field])
        self.assertTrue(state["operational_fault_assessment"]["recovery_notification_required"])
        self.assertFalse(state["operational_fault_assessment"]["existing_material_input_quality_alert_policy_changed"])
        self.assertEqual(encode(state), raw)

    def test_naive_or_inconsistent_issue_time_rejected(self):
        for time in ("2026-09-27T21:56:29.128", "2026-09-27T22:56:29.128-05:00"):
            self.state["snapshot_time_ct"] = time
            with self.assertRaises(ValueError):
                binding.project(encode(self.state))

    def test_invalid_probability_and_duplicate_dates_rejected(self):
        for central in (float("nan"), True, 101, -1):
            state = copy.deepcopy(self.state)
            state["outlook"][0]["point_clear_central_percent"] = central
            with self.assertRaises(ValueError):
                binding.project(encode(state))
        self.state["outlook"].append(self.state["outlook"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            binding.project(encode(self.state))

    def test_real_cli_snapshot_only_update_fails_then_rebinds_idempotently(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model_data").mkdir()
            (root / binding.SNAPSHOT).write_bytes(self.raw)
            stale = copy.deepcopy(self.forecast)
            stale.update(issue_time="2026-09-27T21:47:42-05:00", input_snapshot_hash="0" * 64, input_commit_sha="6" * 40)
            stale["missing_inputs"] = ["Earlier public viewing status"]
            (root / binding.FORECAST).write_bytes(encode(stale))

            def cli(*args):
                return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args], capture_output=True, text=True)

            before = (root / binding.FORECAST).read_bytes()
            result = cli("--check")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("input_snapshot_hash", result.stderr)
            self.assertEqual((root / binding.FORECAST).read_bytes(), before)
            self.assertEqual(cli().returncode, 0)
            corrected = (root / binding.FORECAST).read_bytes()
            self.assertEqual(cli("--check").returncode, 0)
            self.assertEqual(cli().returncode, 0)
            self.assertEqual((root / binding.FORECAST).read_bytes(), corrected)
            self.assertEqual((root / binding.SNAPSHOT).read_bytes(), self.raw)
            self.state["outlook"][0]["point_clear_central_percent"] = 5
            (root / binding.SNAPSHOT).write_bytes(encode(self.state))
            self.assertEqual(cli().returncode, 1)
            self.assertEqual((root / binding.FORECAST).read_bytes(), corrected)

    def test_ci_covers_snapshot_only_and_forecast_only_changes(self):
        workflow = (ROOT / ".github/workflows/forecast_consistency.yml").read_text()
        for path in (binding.SNAPSHOT, binding.FORECAST, "model_data/bind_current_forecast.py"):
            self.assertEqual(workflow.count(f'- "{path}"'), 2)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("python -B model_data/bind_current_forecast.py --check", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("continue-on-error", workflow)
        self.assertEqual(workflow.count('- "tests/fixtures/forecast_binding/**"'), 2)


class ProductionSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.raw = (FIXTURES / "current_state_snapshot_20260928T0016.json").read_bytes()
        self.old_forecast_raw = (FIXTURES / "current_forecast_20260928T0016.json").read_bytes()
        self.state = json.loads(self.raw)
        self.old_forecast = json.loads(self.old_forecast_raw)

    def repaired(self):
        # Explicit fixture repair only: the application must never infer these
        # attestations from prose or fetch them from a potentially stale forecast.
        state = copy.deepcopy(self.state)
        state["probability_basis"] = {
            "probability_type": "HEURISTIC_JUDGMENT_NOT_EMPIRICALLY_CALIBRATED",
            "numeric_change_from_prior_snapshot": 0,
            "reassessment_method": self.old_forecast["method"],
            "summary": self.state["probability_basis"],
        }
        return state

    def test_exact_failure_fixture_has_valid_hash_but_invalid_schema(self):
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(),
                         "c9288fb907e45f9a3ceb28504bdd1de059749cff2d5cf68ff079349e55bc335e")
        self.assertEqual(self.old_forecast["input_snapshot_hash"], hashlib.sha256(self.raw).hexdigest())
        with self.assertRaisesRegex(ValueError, "probability_basis must be an object"):
            binding.check(self.raw, self.old_forecast)

    def test_explicit_repair_projects_full_production_shape_without_reassessment(self):
        state = self.repaired()
        before = encode(state)
        forecast = binding.project(before)
        binding.check(before, forecast)
        self.assertEqual(encode(state), before)
        self.assertEqual({k: v for k, v in state.items() if k != "probability_basis"},
                         {k: v for k, v in self.state.items() if k != "probability_basis"})
        for field in ("issue_time", "input_commit_sha", "missing_inputs", "alert_gates",
                      "notification_condition_met", "forecast_weights_changed", "method",
                      "alert_threshold_percent", "alert_comparator"):
            self.assertEqual(forecast[field], self.old_forecast[field], field)
        for old, new in zip(self.old_forecast["outlooks"], forecast["outlooks"]):
            for key in ("cell", "range_percent", "central_percent", "confidence"):
                self.assertEqual(old[key], new[key])
            self.assertEqual(old["forecast_window"]["date_ct"], new["forecast_window"]["date_ct"])
        self.assertEqual(len(forecast["outlooks"]), 6)
        self.assertEqual(forecast["data_coverage"]["fresh_river_series"], 12)
        self.assertEqual(forecast["data_coverage"]["private_camera_metadata_pass"], 6)
        self.assertEqual(forecast["data_coverage"]["asos_stations"], "KBFM/KMOB UNKNOWN")
        self.assertTrue(forecast["alert_gates"]["material_critical_input_fault"])
        self.assertFalse(forecast["alert_gates"]["point_clear_over_20_percent"])

    def test_production_station_envelope_rejects_schema_or_admission_defects(self):
        malformed = [None, {}, {"status": "UNKNOWN_STALE"}, {"parameters": {}},
                     {"status": "UNKNOWN_STALE", "parameters": "UNKNOWN"},
                     {"status": "UNKNOWN_STALE", "parameters": {}},
                     {"status": "UNKNOWN", "parameters": {"wind": "UNKNOWN"}},
                     {"status": "UNKNOWN", "parameters": {"wind": {"value_status": "typo"}}}]
        valid = next(r for r in self.state["input_rows"] if r["source"] == "NOAA/NWS ASOS KBFM and KMOB")["parameter_admission"]["KBFM"]
        for mutation in (dict(valid, status="typo"), dict(valid, status="KNOWN"),
                         dict(valid, extra="ambiguous")):
            malformed.append(mutation)
        false_stale = copy.deepcopy(valid)
        del false_stale["parameters"]["wind_speed"]["admission_reason"]
        malformed.append(false_stale)
        for admission in malformed:
            with self.subTest(admission=admission):
                state = self.repaired()
                row = next(r for r in state["input_rows"] if r["source"] == "NOAA/NWS ASOS KBFM and KMOB")
                row["parameter_admission"]["KBFM"] = admission
                with self.assertRaisesRegex(ValueError, "ASOS parameter_admission"):
                    binding.project(encode(state))

    def test_invalid_production_snapshot_never_writes_in_check_or_bind_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "model_data").mkdir()
            (root / binding.SNAPSHOT).write_bytes(self.raw)
            (root / binding.FORECAST).write_bytes(self.old_forecast_raw)
            for args in ([], ["--check"]):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "--root", str(root), *args],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 1)
                self.assertIn("probability_basis must be an object", result.stderr)
                self.assertNotIn("string indices", result.stderr)
                self.assertEqual((root / binding.SNAPSHOT).read_bytes(), self.raw)
                self.assertEqual((root / binding.FORECAST).read_bytes(), self.old_forecast_raw)
                self.assertFalse(list(root.rglob("*.tmp")))

    def test_parser_errors_and_nonobject_snapshots_are_not_coerced(self):
        with self.assertRaises(json.JSONDecodeError):
            binding.project(self.raw[:-2])
        for value in ([], None, "snapshot"):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "Snapshot must be a JSON object"):
                    binding.project(encode(value))


if __name__ == "__main__":
    unittest.main()
