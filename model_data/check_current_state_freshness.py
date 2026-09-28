"""Read-only source/snapshot lag check. Never synthesize state or forecast.

Admissibility is evaluated at the source's retrieval/capture time so an overdue
reconciliation cannot turn green merely because unconsumed evidence ages out.
This is separate from issue-time sensor QC and exact forecast binding.
"""
import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = "model_data/current_state_snapshot.json"
MAX_LAG_MINUTES = 30
MODEL_PRODUCTS = (
    "ngofs2_point_clear_nowcast", "ngofs2_point_clear_forecast",
    "ngofs2_mobile_bay_named_stations_nowcast",
    "ngofs2_mobile_bay_named_stations_forecast", "ngofs2_shoreline_grid",
)
PRODUCTS = ("cameras", "asos_weather", "river_forcing", "weeks_bay_realtime") + MODEL_PRODUCTS
# Refresh bookkeeping is not new evidence. All remaining row fields (including
# QC, units, location, method and vertical identity) are part of the fingerprint.
BOOKKEEPING = {"available_at", "ingested_at", "retrieved_at_utc", "source_hash"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stamp(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(dt.utcoffset() is not None, "timestamp lacks UTC offset")
    return dt.astimezone(timezone.utc)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def semantic_rows(rows):
    return sorted(canonical({k: v for k, v in row.items() if k not in BOOKKEEPING}) for row in rows)


class Reader:
    """Current checkout or exact snapshot provenance, with no network/writes."""
    def __init__(self, root, snapshot=None):
        self.root, self.snapshot, self.hashes = root.resolve(), snapshot, {}

    def read(self, path):
        target = (self.root / path).resolve()
        require(target.is_relative_to(self.root), "source path escapes repository")
        if self.snapshot is None:
            data = target.read_bytes()
        else:
            provenance = self.snapshot["reconciliation"]["source_provenance"].get(path)
            if provenance:
                expected = provenance["sha256"]
                require(re.fullmatch(r"[0-9a-f]{64}", expected), "invalid provenance digest")
                if target.is_file() and digest(target.read_bytes()) == expected:
                    data = target.read_bytes()
                else:
                    blob = provenance.get("git_blob", provenance.get("blob_sha", ""))
                    require(re.fullmatch(r"[0-9a-f]{40}", blob), "missing provenance blob: " + path)
                    data = self.git("cat-file", "blob", blob)
                require(digest(data) == expected, "provenance hash mismatch: " + path)
            else:
                # Raw archives and normalized products need not each be listed;
                # resolve them only from the snapshot's explicit evidence commit.
                commit = self.snapshot["reconciliation"]["input_commit_sha"]
                require(re.fullmatch(r"[0-9a-f]{40}", commit), "invalid evidence commit")
                data = self.git("show", commit + ":" + path)
        self.hashes[path] = digest(data)
        return data

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True)
        require(result.returncode == 0, "provenance object unavailable; use a full-history checkout")
        return result.stdout

    def json(self, path):
        return json.loads(self.read(path))

    def csv(self, path):
        return list(csv.DictReader(io.StringIO(self.read(path).decode("utf-8"))))

    def archive(self, path, expected):
        data = gzip.decompress(self.read("model_data/" + path))
        require(digest(data) == expected, "archive digest mismatch: " + path)
        return data


def candidate(rows, available, evidence_time=None, detail=None):
    return {"fingerprint": digest(canonical(rows).encode()),
            "available_at": available, "evidence_time": evidence_time or available,
            "admissible": bool(rows), "detail": detail or "validated published context"}


def camera_product(reader, now):
    status, burst, vision = (reader.json(p) for p in ("status.json", "burst_status.json", "vision.json"))
    cycle = stamp(status["capture_time_ct"])
    require(cycle == stamp(burst["capture_time_ct"]) == stamp(vision["capture_time_ct"]),
            "incoherent camera cycle")
    require(cycle <= now, "future camera cycle")
    registry = reader.json("model_data/camera_sources.json")
    ids = sorted(c["camera_id"] for c in registry["cameras"] if c["access"] == "owner_google")
    require(bool(ids), "no expected cameras")
    records, times = [], [cycle]
    for cid in ids:
        s, b, v = (doc.get("cameras", {}).get(cid, {}) for doc in (status, burst, vision))
        require(bool(s) and bool(b) and bool(v), "missing camera metadata: " + cid)
        if s.get("ok") is not True:
            require(b.get("ok") is not True and v.get("status") != "ok", "conflicting camera health: " + cid)
            records.append({"id": cid, "state": "UNKNOWN_CAPTURE_FAILED"})
            continue
        shots = b.get("shots", [])
        require(b.get("ok") is True and len(shots) == 3, "invalid temporal burst: " + cid)
        shot_times = [stamp(x["timestamp_ct"]) for x in shots]
        require(all(5 <= (shot_times[i+1] - shot_times[i]).total_seconds() <= 30 for i in (0, 1)),
                "invalid burst spacing: " + cid)
        require(cycle <= shot_times[0] <= shot_times[-1] <= now
                and stamp(s["timestamp_ct"]) == shot_times[-1], "camera timestamp mismatch: " + cid)
        require(v.get("status") == "ok" and v.get("burst_shots") == shots, "vision shot mismatch: " + cid)
        pixels = reader.read(cid + ".jpg")
        require(len(pixels) == s["bytes"] == shots[-1]["bytes"], "camera image size mismatch: " + cid)
        records.append({"id": cid, "status": s, "burst": b, "vision": v, "image_sha256": digest(pixels)})
        times.extend(shot_times)
    limit = reader.json("model_data/sensor_contract.json")["freshness_minutes"]["camera"]
    require((max(times) - cycle).total_seconds()/60 <= limit, "camera cycle exceeds freshness policy")
    # Failed captures are admissible health context, never biological negatives.
    return candidate({"cycle": cycle.isoformat(), "cameras": records}, max(times), cycle,
                     "coherent metadata and latest images; no desktop/archive or biological acceptance")


def environmental_product(name, reader, now):
    m = reader.json("model_data/" + name + "_manifest.json")
    available = stamp(m.get("retrieved_at_utc", m.get("retrieved_at", m.get("started_at_utc"))))
    require(available <= now, "future source retrieval")
    if m["status"] == "unavailable":
        return candidate([], available, detail="declared unavailable; retain UNKNOWN")
    require(m["status"] == "complete" or (name == "weeks_bay_realtime" and m["status"] == "partial"),
            "producer failed or unrecognized status: " + str(m["status"]))
    limits = reader.json("model_data/sensor_contract.json")["freshness_minutes"]
    if name == "asos_weather":
        payload = reader.read("model_data/asos_weather_normalized.json")
        require(digest(payload) == m["normalized_sha256"], "ASOS manifest/data hash mismatch")
        rows = json.loads(payload)
        require(len(rows) == m["normalized_rows"], "ASOS row count mismatch")
        rows = [r for r in rows if r["value_status"] in ("KNOWN", "TRACE")
                and r["qc_flag"] == "LOCAL_CHECKS_PASS"
                and (r["value_status"] == "TRACE" or
                     (r["value"] is not None and math.isfinite(float(r["value"]))))
                and stamp(r["available_at"]) <= available
                and 0 <= (available - stamp(r["observed_at_utc"])).total_seconds()/60 <= limits["weather"]]
        time_key = "observed_at_utc"
    elif name == "river_forcing":
        # Reuse the producer's qualifier/method rules and validate the raw digest.
        from ingest_river_forcing import normalize
        raw = reader.archive(m["raw_path"], m["raw_sha256"])
        rows = normalize(json.loads(raw), available, m["source_url"])
        require(len(rows) == m["normalized_rows"], "river row count mismatch")
        rows = latest(rows, ("series_id",), "observed_at_utc")
        rows = [r for r in rows if r["research_qc_eligible"] and
                0 <= (available - stamp(r["observed_at_utc"])).total_seconds()/60 <= limits["regional_proxy"]]
        time_key = "observed_at_utc"
    elif name == "weeks_bay_realtime":
        from ingest_weeks_bay_realtime import parse_met, parse_ocean
        parsed = []
        for source in m["sources"]:
            if source["status"] != "complete":
                continue
            parser = {"WKXA1": parse_met, "WKQA1": parse_ocean}[source["station_id"]]
            raw = reader.archive(source["raw_path"], source["raw_sha256"])
            parsed.extend(parser(raw.decode("utf-8"), available))
        rows = reader.csv("model_data/weeks_bay_realtime_normalized.csv")
        require(len(rows) == m["normalized_rows"] == len(parsed), "Weeks Bay row count mismatch")
        # CSV scalar rendering must match the validated archive reparse.
        rendered = [{k: "" if v is None else str(v) for k, v in r.items()} for r in parsed]
        require(semantic_rows(rows) == semantic_rows(rendered), "Weeks Bay archive/data mismatch")
        rows = latest(rows, ("station_id", "parameter"), "observed_at")
        rows = [r for r in rows if r["qc_status"] == "NDBC_REALTIME_AUTOMATED_QC"
                and 0 <= (available - stamp(r["observed_at"])).total_seconds()/60 <= limits["regional_proxy"]]
        time_key = "observed_at"
    else:
        path = m.get("normalized_csv", m.get("normalized_data"))
        rows = reader.csv("model_data/" + path)
        require(bool(rows) and len(rows) == m["normalized_rows"], "model row count mismatch")
        archive = m.get("subset_archive", m.get("raw_subset_archive"))
        expected = m.get("subset_sha256", m.get("raw_subset_sha256"))
        raw = json.loads(reader.archive(archive, expected))
        # Grid archives contain source slices; station archives contain exact rows.
        if "rows" in raw:
            rendered = [{k: "" if v is None else str(v) for k, v in r.items()} for r in raw["rows"]]
            require(semantic_rows(rows) == semantic_rows(rendered), "model archive/data mismatch")
        for r in rows:
            require(r.get("evidence_class", r.get("source_class")) == "MODEL", "model/observation identity mismatch")
            require(stamp(r["model_initialized_at"]) <= available and stamp(r["available_at"]) <= available,
                    "model not available at retrieval")
            stamp(r["valid_at"])  # Future model valid times are allowed, never observations.
            require(math.isfinite(float(r.get("value", r.get("value_or_status")))), "invalid model value")
        time_key = "model_initialized_at"
    return candidate(semantic_rows(rows), available, max((stamp(r[time_key]) for r in rows), default=available),
                     "admissible at retrieval; zero-weight context only" if rows else "no admissible rows; retain UNKNOWN")


def latest(rows, keys, time_key):
    times = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        times[key] = max(times.get(key, stamp(row[time_key])), stamp(row[time_key]))
    # Retain conflicting same-time rows for fingerprinting; never choose a value.
    return [r for r in rows if stamp(r[time_key]) == times[tuple(r[k] for k in keys)]]


def inspect(root, now, products=PRODUCTS):
    snapshot = json.loads((root / SNAPSHOT).read_bytes())
    issue = stamp(snapshot["snapshot_time_ct"])
    require(issue <= now, "future snapshot issue time")
    require(isinstance(snapshot["reconciliation"]["source_provenance"], dict), "missing snapshot provenance")
    age = (now - issue).total_seconds()/60
    results = []
    for name in products:
        item = {"source": name}
        try:
            current_reader, baseline_reader = Reader(root), Reader(root, snapshot)
            read = camera_product if name == "cameras" else lambda r, t: environmental_product(name, r, t)
            current = read(current_reader, now)
            item.update(available_at_utc=current["available_at"].isoformat(),
                        evidence_time_utc=current["evidence_time"].isoformat(),
                        source_to_snapshot_gap_minutes=round((current["available_at"] - issue).total_seconds()/60, 3),
                        detail=current["detail"], source_hashes=current_reader.hashes)
            if not current["admissible"]:
                item["status"] = "SOURCE_UNAVAILABLE"
            else:
                baseline = read(baseline_reader, issue)
                same = current["fingerprint"] == baseline["fingerprint"]
                item.update(snapshot_source_hashes=baseline_reader.hashes,
                            fingerprint=current["fingerprint"], snapshot_fingerprint=baseline["fingerprint"])
                item["status"] = "CURRENT" if same else ("STALE" if age > MAX_LAG_MINUTES else "PENDING_RECONCILIATION")
                if not same:
                    item["reason"] = ("NEWER_SOURCE_EVIDENCE" if current["evidence_time"] > baseline["evidence_time"]
                                      else "SOURCE_CONTENT_CORRECTION_OR_COVERAGE_CHANGE")
        except (OSError, ValueError, KeyError, TypeError, EOFError) as error:
            item.update(status="ERROR", reason=str(error))
        results.append(item)
    states = {r["status"] for r in results}
    status = next((s for s in ("ERROR", "STALE", "PENDING_RECONCILIATION") if s in states), "CURRENT")
    return {"schema_version": "1.0", "status": status, "checked_at_utc": now.isoformat(),
            "snapshot_time_ct": snapshot["snapshot_time_ct"], "snapshot_sha256": digest((root / SNAPSHOT).read_bytes()),
            "snapshot_age_minutes": round(age, 3), "max_reconciliation_lag_minutes": MAX_LAG_MINUTES,
            "scope": "source drift only; not sensor health, probability validity or desktop/dawn acceptance",
            "sources": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--as-of", help="Offset-aware clock for deterministic offline replay")
    args = parser.parse_args()
    try:
        report = inspect(args.root, stamp(args.as_of) if args.as_of else datetime.now(timezone.utc))
    except (OSError, ValueError, KeyError, TypeError) as error:
        report = {"status": "ERROR", "reason": str(error)}
    print(json.dumps(report, indent=2, allow_nan=False))
    return 1 if report["status"] in ("ERROR", "STALE") else 0


if __name__ == "__main__":
    raise SystemExit(main())
