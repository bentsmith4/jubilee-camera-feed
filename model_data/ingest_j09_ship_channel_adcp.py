#!/usr/bin/env python3
"""Research-only RDI PD0/WinRiver SHIP-frame ingest for GRIIDC Y1.x122.038:0002.

Run against preserved native DAT files. No network fetch, timezone inference,
navigation association, vessel-motion correction or Earth rotation is performed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from datetime import datetime, timezone
from pathlib import Path

SOURCE_ID = "griidc_y1_x122_038_0002_mobile_bay_ship_channel_adcp_2010"
FIELDS = ("observation_id", "source_id", "raw_sha256", "raw_path", "byte_offset",
          "ensemble_number", "bin_index", "component_index", "ship_component", "velocity_mm_s",
          "source_clock", "source_clock_timezone", "navigation_association",
          "latitude", "longitude", "coordinate_frame", "velocity_units",
          "bin_size_cm", "blanking_cm", "transducer_draft_m", "vertical_reference",
          "geometry_status", "qc_status", "available_at", "ingested_at",
          "production_weight")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blocks(data: bytes):
    """Yield checksum-valid PD0 records and offsets; skip arbitrary WinRiver bytes."""
    pos = 0
    while pos + 8 <= len(data):
        start = data.find(b"\x7f\x7f", pos)
        if start < 0 or start + 8 > len(data):
            break
        length = int.from_bytes(data[start + 2:start + 4], "little")
        ntypes = data[start + 5]
        end = start + length + 2  # PD0 length excludes trailing 16-bit checksum
        if length < 6 + 2 * ntypes or end > len(data):
            pos = start + 1
            continue
        record = data[start:end]
        if sum(record[:-2]) & 0xffff != int.from_bytes(record[-2:], "little"):
            pos = start + 1
            continue
        offsets = [int.from_bytes(record[6 + 2*i:8 + 2*i], "little") for i in range(ntypes)]
        if len(set(offsets)) != len(offsets) or any(o < 6 + 2*ntypes or o + 2 > length for o in offsets):
            pos = start + 1
            continue
        sections = {}
        for o in offsets:
            next_o = min((x for x in offsets if x > o), default=length)
            section_id = int.from_bytes(record[o:o+2], "little")
            if section_id in sections:
                sections = {}
                break
            sections[section_id] = record[o:next_o]
        if not sections:
            pos = start + 1
            continue
        yield start, sections
        pos = end


def decode(data: bytes, raw_path: str, ingested_at: str):
    digest = sha256(data)
    rows = []
    ensembles = 0
    rejected = 0
    for offset, sections in blocks(data):
        fixed, variable, velocity = (sections.get(k) for k in (0, 0x80, 0x100))
        if not fixed or not variable or not velocity or len(fixed) < 30 or len(variable) < 12:
            rejected += 1
            continue
        cells = fixed[9]
        transform = (fixed[25] >> 3) & 3
        # RDI coordinate transformation: 0 beam, 1 instrument, 2 ship, 3 earth.
        if transform != 2 or not 0 < cells <= 255 or len(velocity) < 2 + 8*cells:
            rejected += 1
            continue
        rtc = variable[4:11]
        year = (2000 if rtc[0] < 80 else 1900) + rtc[0]
        try:
            if rtc[6] > 99:
                raise ValueError("invalid hundredths")
            clock = datetime(year, *rtc[1:6]).strftime("%Y-%m-%d %H:%M:%S") + f".{rtc[6]:02d}"
        except ValueError:
            rejected += 1
            continue
        ensemble = int.from_bytes(variable[2:4], "little")
        bin_size = int.from_bytes(fixed[12:14], "little")
        blanking = int.from_bytes(fixed[14:16], "little")
        ensembles += 1
        for cell in range(cells):
            for component in range(4):
                value = struct.unpack_from("<h", velocity, 2 + cell*8 + component*2)[0]
                rows.append({
                    "observation_id": sha256(f"{digest}:{offset}:{cell}:{component}".encode()),
                    "source_id": SOURCE_ID, "raw_sha256": digest, "raw_path": raw_path,
                    "byte_offset": offset, "ensemble_number": ensemble,
                    "bin_index": cell + 1, "component_index": component + 1,
                    "ship_component": ("port_starboard", "aft_forward", "to_surface", "error_velocity")[component],
                    "velocity_mm_s": "" if value == -32768 else value,
                    "source_clock": clock, "source_clock_timezone": "UNKNOWN",
                    "navigation_association": "UNRESOLVED", "latitude": "", "longitude": "",
                    "coordinate_frame": "SHIP", "velocity_units": "mm/s (native PD0)",
                    "bin_size_cm": bin_size, "blanking_cm": blanking,
                    "transducer_draft_m": "", "vertical_reference": "UNRESOLVED",
                    "geometry_status": "SHIP_CHANNEL_NOT_POINT_CLEAR",
                    "qc_status": "MISSING_NATIVE_VALUE" if value == -32768 else "RAW_UNQC",
                    "available_at": "UNRESOLVED", "ingested_at": ingested_at,
                    "production_weight": 0,
                })
    return rows, ensembles, rejected


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", type=Path, help="Preserved native PD0/WinRiver files")
    ap.add_argument("--output-dir", required=True, type=Path)
    args = ap.parse_args()
    inputs = sorted(args.inputs)
    if (len(set(inputs)) != len(inputs) or len({p.name for p in inputs}) != len(inputs)
            or any(not p.is_file() for p in inputs)):
        ap.error("each input must be an existing file with a distinct basename")
    now = datetime.now(timezone.utc).isoformat()
    all_rows, objects, raw_data = [], [], {}
    for path in inputs:
        data = path.read_bytes()
        raw_data[sha256(data)] = data
        rows, count, rejected = decode(data, path.name, now)
        objects.append({"name": path.name, "bytes": len(data), "sha256": sha256(data),
                        "raw_archive": f"raw/{sha256(data)}.dat",
                        "pd0_ship_ensembles": count, "rejected_pd0_records": rejected})
        all_rows.extend(rows)
    if not all_rows:
        ap.error("no checksum-valid SHIP-frame PD0 velocity rows; no ingest artifacts written")
    if len({r['observation_id'] for r in all_rows}) != len(all_rows):
        ap.error("duplicate source bytes/record identities; no ingest artifacts written")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / "raw"
    archive.mkdir(exist_ok=True)
    for digest, data in raw_data.items():
        target = archive / f"{digest}.dat"
        if target.exists():
            if target.read_bytes() != data:
                ap.error(f"immutable raw hash collision at {target}")
        else:
            with target.open("xb") as f:
                f.write(data)
    out = args.output_dir / "j09_ship_channel_adcp_ship_frame.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader(); writer.writerows(all_rows)
    manifest = {
        "schema_version": "1.0", "source_id": SOURCE_ID, "doi": "10.7266/N7B85630",
        "research_only": True, "status": "SHIP_FRAME_RAW_UNQC", "generated_at": now,
        "raw_objects": objects, "normalized_rows": len(all_rows),
        "normalized_csv": out.name, "normalized_sha256": sha256(out.read_bytes()),
        "raw_preservation": "Exact input bytes copied to raw/<sha256>.dat; retain original survey paths and provider inventory separately.",
        "source_clock_timezone": "UNRESOLVED; never treated as UTC",
        "navigation": "No RMC-to-ensemble association asserted; four reviewed suspect associations remain unresolved, maximum noted offset approximately 294 seconds.",
        "frame": "SHIP only; no Earth-frame or Point Clear shore-normal current validated",
        "geometry": "Deployment, compass/heading, magnetic variation, draft/transducer, vertical-bin reference and bottom/side-lobe QC unresolved",
        "provider_zip_sha256": None,
        "provider_zip_checksum_status": "UNVERIFIED; reconstructed member CRC/size match is not provider ZIP identity",
        "production_weight": 0, "alert_change": False,
    }
    (args.output_dir / "j09_ship_channel_adcp_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": len(all_rows), "manifest": str(args.output_dir / 'j09_ship_channel_adcp_manifest.json')}))


if __name__ == "__main__":
    main()
