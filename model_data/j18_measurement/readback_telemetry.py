"""Local, exact-hash canonical integrity readback. No network calls or log writes."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'desktop_runtime'))
from attempt_telemetry import bind_integrity, UNKNOWN


def readback(raw, snapshots):
    retained = [(json.loads(payload), payload) for payload in snapshots]
    rows = []
    for line in raw.splitlines():
        row = json.loads(line)
        matches = [bind_integrity(row, snapshot, payload) for snapshot, payload in retained]
        matches = [m for m in matches if m['canonical_integrity_receipt_sha256'] != UNKNOWN]
        # Conflicting/duplicate candidates are a gap, never choose favorable evidence.
        binding = matches[0] if len(matches) == 1 else dict(
            camera_integrity=UNKNOWN, canonical_integrity_receipt_sha256=UNKNOWN)
        rows.append(dict(attempt_id=row.get('attempt_id', UNKNOWN), stage=row['stage'],
                         runtime_version=row.get('runtime_version', UNKNOWN),
                         **binding))
    return dict(status='RESEARCH_ONLY_READBACK', attempts=len(rows), rows=rows,
                matched_attempts=sum(r['canonical_integrity_receipt_sha256'] != UNKNOWN for r in rows),
                production_changes=[])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--usage', type=Path, required=True)
    p.add_argument('--snapshot', type=Path, action='append', default=[])
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.write_text(json.dumps(readback(a.usage.read_bytes(), [s.read_bytes() for s in a.snapshot]), indent=2)+'\n')


if __name__ == '__main__':
    main()
