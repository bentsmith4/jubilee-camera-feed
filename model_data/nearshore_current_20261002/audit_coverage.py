"""Offline source/geometry audit. This does not ingest or accept velocity rows."""
import hashlib
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def distance_km(lat, lon, reference):
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("Invalid geographical coordinate")
    a, b = math.radians(lat), math.radians(reference["lat"])
    dlat = a - b
    dlon = math.radians(lon - reference["lon"])
    h = math.sin(dlat / 2) ** 2 + math.cos(a) * math.cos(b) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(min(1, h)))


def audit():
    contract_bytes = (HERE / "acceptance_contract.json").read_bytes()
    contract = json.loads(contract_bytes)
    inventory = json.loads((HERE / "source_inventory.json").read_text())
    if hashlib.sha256(contract_bytes).hexdigest() != inventory["contract_sha256"]:
        raise ValueError("Preregistered contract changed")
    receipts = json.loads((HERE / "retrieval_receipt.json").read_text())
    for receipt in receipts:
        if receipt["status"] == 200:
            raw = (ROOT / receipt["raw_file"]).read_bytes()
            if receipt["raw_file"].endswith(".gz"):
                raw = gzip.decompress(raw)
            if len(raw) != receipt["bytes"] or hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
                raise ValueError("Source snapshot checksum failed: " + receipt["id"])
    rows = []
    for candidate in inventory["candidates"]:
        distance = distance_km(candidate["lat"], candidate["lon"], contract["reference"])
        rows.append({
            "id": candidate["id"], "point_clear_distance_km": round(distance, 4) if distance is not None else None,
            "materially_closer_geometry_screen": None if distance is None else distance <= contract["geometry_screen"]["materially_closer_point_clear_km"],
            "disposition": candidate["disposition"], "scientific_acceptance": "NOT_PERFORMED_NO_VELOCITY_PAYLOAD",
        })
    return {
        "scope": "RESEARCH_ONLY", "production_action": "NO_CHANGE",
        "contract_sha256": inventory["contract_sha256"],
        "status": "NO_SUITABLE_CLOSER_PUBLIC_DATASET_VERIFIED",
        "absence_of_all_datasets_proven": False,
        "accepted_earth_frame_rows": 0, "velocity_payloads_downloaded": 0,
        "predictive_skill": "NOT_ESTIMABLE", "candidates": rows,
        "unresolved_lead_count": len(inventory["unresolved_search_leads"]),
    }


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
