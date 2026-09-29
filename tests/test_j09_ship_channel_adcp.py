import sys
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "model_data"))
import ingest_j09_ship_channel_adcp as ingest


def packet(frame=2, corrupt=False, bad_clock=False, missing=False):
    fixed = bytearray(30)
    fixed[:2] = b"\x00\x00"
    fixed[9] = 1
    fixed[12:14] = (50).to_bytes(2, "little")
    fixed[14:16] = (25).to_bytes(2, "little")
    fixed[25] = frame << 3
    variable = bytearray(12)
    variable[:2] = b"\x80\x00"
    variable[2:4] = (42).to_bytes(2, "little")
    variable[4:11] = bytes([10, 8, 18, 12, 34, 56, 70 if not bad_clock else 255])
    velocity = b"\x00\x01" + (b"\x00\x80" if missing else (123).to_bytes(2, "little", signed=True)) + b"\x00\x00"*3
    offsets = [12, 42, 54]
    body = b"\x7f\x7f" + (64).to_bytes(2, "little") + bytes([0, 3])
    body += b"".join(o.to_bytes(2, "little") for o in offsets)
    body += fixed + variable + velocity
    assert len(body) == 64
    checksum = (sum(body) + corrupt) & 0xffff
    return body + checksum.to_bytes(2, "little")


class PD0Tests(unittest.TestCase):
    def test_ship_rows_preserve_units_clock_and_gates(self):
        payload = b"WinRiver noise" + packet() + b"tail"
        rows, count, rejected = ingest.decode(payload, "survey.DAT", "ingest-time")
        self.assertEqual((count, rejected, len(rows)), (1, 0, 4))
        self.assertEqual(rows[0]["source_clock"], "2010-08-18 12:34:56.70")
        self.assertEqual(rows[0]["velocity_mm_s"], 123)
        self.assertEqual(rows[0]["ship_component"], "port_starboard")
        self.assertEqual(rows[0]["coordinate_frame"], "SHIP")
        self.assertEqual(rows[0]["navigation_association"], "UNRESOLVED")
        self.assertEqual(rows[0]["source_clock_timezone"], "UNKNOWN")
        self.assertEqual(rows[0]["production_weight"], 0)
        self.assertEqual(rows[0]["raw_sha256"], ingest.sha256(payload))

    def test_checksum_and_frame_rejected(self):
        rows, count, rejected = ingest.decode(packet(corrupt=True) + packet(frame=3), "x", "t")
        self.assertEqual((rows, count, rejected), ([], 0, 1))

    def test_invalid_clock_rejected_and_missing_velocity_flagged(self):
        rows, count, rejected = ingest.decode(packet(bad_clock=True) + packet(missing=True), "x", "t")
        self.assertEqual((count, rejected), (1, 1))
        self.assertEqual(rows[0]["velocity_mm_s"], "")
        self.assertEqual(rows[0]["qc_status"], "MISSING_NATIVE_VALUE")

    def test_stable_identity_and_no_navigation_inference(self):
        a = ingest.decode(packet(), "a", "now")[0]
        b = ingest.decode(packet(), "b", "later")[0]
        self.assertEqual(a[0]["observation_id"], b[0]["observation_id"])
        self.assertEqual(a[0]["latitude"], "")

    def test_cli_archives_exact_bytes_and_binds_output(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "20100818.DAT"
            source.write_bytes(packet())
            output = root / "out"
            subprocess.run([sys.executable, str(Path(ingest.__file__)),
                            "--output-dir", str(output), str(source)], check=True,
                           capture_output=True)
            manifest = json.loads((output / "j09_ship_channel_adcp_manifest.json").read_text())
            digest = ingest.sha256(source.read_bytes())
            self.assertEqual((output / "raw" / f"{digest}.dat").read_bytes(), source.read_bytes())
            self.assertEqual(manifest["raw_objects"][0]["sha256"], digest)
            self.assertEqual(manifest["normalized_sha256"], ingest.sha256(
                (output / manifest["normalized_csv"]).read_bytes()))
            self.assertEqual(manifest["production_weight"], 0)


if __name__ == "__main__":
    unittest.main()
