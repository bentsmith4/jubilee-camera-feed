import ast
import io
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "research"))
from contact_sheet_probe import build_contact_sheet, prepare_comparison


def fixture(size=(640, 360)):
    frames = []
    for i in range(3):
        im = Image.new("RGB", size, (i*40, 50, 70))
        draw = ImageDraw.Draw(im)
        # Moving one-pixel point, fine lines, and corners expose fidelity loss.
        draw.point((100+i, 80), fill="white")
        draw.line((0, 100+i, size[0]-1, 100+i), fill="yellow", width=1)
        draw.point((size[0]-1, size[1]-1), fill="red")
        b = io.BytesIO()
        im.save(b, format="JPEG", quality=95)
        frames.append(b.getvalue())
    shots = [{"shot": i+1, "timestamp_ct": f"2026-09-27T06:30:{i*10:02d}-05:00",
              "timing": "actual_screenshot_time" if i != 1 else "nominal_estimate"}
             for i in range(3)]
    return frames, shots


class ContactSheetTests(unittest.TestCase):
    def test_exact_pixels_order_and_timing(self):
        frames, shots = fixture()
        png, metadata = build_contact_sheet(frames, shots, "test")
        with Image.open(io.BytesIO(png)) as sheet:
            for raw, panel, shot in zip(frames, metadata["panels"], shots):
                with Image.open(io.BytesIO(raw)) as original:
                    self.assertEqual(sheet.crop(panel["box"]).tobytes(), original.convert("RGB").tobytes())
                self.assertEqual(panel["timestamp_ct"], shot["timestamp_ct"])
                self.assertEqual(panel["timing"], shot["timing"])

    def test_requests_and_unproven_savings(self):
        frames, shots = fixture()
        base, candidate, report = prepare_comparison(frames, shots, "test")
        self.assertEqual((len(base), len(candidate)), (3, 1))
        self.assertEqual(report["request_count_savings"], 0)
        self.assertTrue(report["pixel_roundtrip_exact"])
        self.assertIsNone(report["detection_equivalence"])
        self.assertFalse(report["production_enabled"])

    def test_missing_frame_rejected(self):
        frames, shots = fixture()
        with self.assertRaises(ValueError):
            build_contact_sheet(frames[:2], shots, "test")

    def test_reversed_or_duplicate_timestamps_rejected(self):
        frames, shots = fixture()
        shots[2]["timestamp_ct"] = shots[0]["timestamp_ct"]
        with self.assertRaises(ValueError):
            build_contact_sheet(frames, shots, "test")

    def test_missing_timezone_rejected(self):
        frames, shots = fixture()
        shots[0]["timestamp_ct"] = "2026-09-27T06:30:00"
        with self.assertRaises(ValueError):
            build_contact_sheet(frames, shots, "test")

    def test_cross_camera_rejected(self):
        frames, shots = fixture()
        shots[1]["camera_id"] = "different"
        with self.assertRaises(ValueError):
            build_contact_sheet(frames, shots, "test")

    def test_mixed_dimensions_rejected(self):
        frames, shots = fixture()
        frames[1] = fixture((800, 450))[0][1]
        with self.assertRaises(ValueError):
            build_contact_sheet(frames, shots, "test")

    def test_missing_provenance_rejected(self):
        frames, shots = fixture()
        del shots[0]["timing"]
        with self.assertRaises(ValueError):
            build_contact_sheet(frames, shots, "test")

    def test_bad_image_rejected(self):
        frames, shots = fixture()
        frames[0] = b"not an image"
        with self.assertRaises(OSError):
            build_contact_sheet(frames, shots, "test")

    def test_production_already_batches_one_request(self):
        tree = ast.parse((ROOT / "desktop_runtime/analyze_frames.py").read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "analyze_burst")
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "api_response"]
        self.assertEqual(len(calls), 1)
        self.assertFalse(any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "api_response" for loop in ast.walk(fn) if isinstance(loop, ast.For) for n in ast.walk(loop)))


if __name__ == "__main__":
    unittest.main()
