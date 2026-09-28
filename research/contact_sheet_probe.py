"""Offline, opt-in contact-sheet feasibility probe. Never imported by live code.

Public media must be supplied transiently by an authorized caller; this module
does not download, persist, or publish media. CLI input is owner-camera files.
Only a metrics report is written. No API requests or production writes occur.
"""
import argparse
import base64
import hashlib
import io
import json
import textwrap
from datetime import datetime
from pathlib import Path
from time import perf_counter

from PIL import Image, ImageDraw

MAX_PIXELS = 32_000_000
HEADER = 72


def build_contact_sheet(frames, shots, camera_id):
    """Return in-memory lossless PNG and metadata; retain every decoded pixel.

    Frames are three encoded images from ONE camera, in chronological order.
    This guarantees local pixel fidelity, not model-side processing fidelity.
    """
    if not camera_id or len(frames) != 3 or len(shots) != 3:
        raise ValueError("Exactly three frames and timestamps from one camera required")
    dates = []
    for i, shot in enumerate(shots, 1):
        if shot.get("shot") != i or shot.get("camera_id", camera_id) != camera_id:
            raise ValueError("Frame order or camera mismatch")
        if not isinstance(shot.get("timing"), str) or not shot["timing"]:
            raise ValueError("Timing provenance required")
        dt = datetime.fromisoformat(shot["timestamp_ct"])
        if dt.utcoffset() is None:
            raise ValueError("Timezone-aware timestamps required")
        dates.append(dt)
    if not dates[0] < dates[1] < dates[2]:
        raise ValueError("Timestamps must strictly increase")
    decoded = []
    for raw in frames:
        with Image.open(io.BytesIO(raw)) as im:
            if im.width < 320 or im.width * im.height > MAX_PIXELS:
                raise ValueError("Unsupported frame dimensions")
            if im.getexif().get(274, 1) != 1:
                raise ValueError("Oriented images require explicit normalization")
            decoded.append(im.convert("RGB"))
    if len({im.size for im in decoded}) != 1:
        raise ValueError("Mixed frame dimensions require review")
    w, h = decoded[0].size
    # Choose the least elongated layout; never downsample or crop to fit.
    layouts = [(3, 1), (1, 3), (2, 2)]
    cols, rows = min(layouts, key=lambda cr: max(cr[0]*w, cr[1]*(h+HEADER)) /
                     min(cr[0]*w, cr[1]*(h+HEADER)))
    size = (cols*w, rows*(h+HEADER))
    if size[0]*size[1] > MAX_PIXELS:
        raise ValueError("Composite exceeds pixel budget; retain separate frames")
    sheet = Image.new("RGB", size, (32, 32, 32))
    draw = ImageDraw.Draw(sheet)
    panels = []
    for index, (im, shot) in enumerate(zip(decoded, shots)):
        x, y = (index % cols)*w, (index // cols)*(h+HEADER)
        label = f"FRAME {index+1} | {shot['timestamp_ct']} | {shot['timing']}"
        lines = textwrap.wrap(label, width=max(1, (w-16)//7))
        if len(lines) > 4:
            raise ValueError("Timing label exceeds header; retain separate frames")
        draw.multiline_text((x+8, y+6), "\n".join(lines), fill="white", spacing=3)
        sheet.paste(im, (x, y+HEADER))
        panels.append({"shot": index+1, "timestamp_ct": shot["timestamp_ct"],
                       "timing": shot["timing"], "box": [x,y+HEADER,x+w,y+HEADER+h],
                       "decoded_rgb_sha256": hashlib.sha256(im.tobytes()).hexdigest()})
    out = io.BytesIO()
    sheet.save(out, format="PNG")
    return out.getvalue(), {"camera_id": camera_id, "layout_columns": cols,
        "sheet_size": list(size), "source_size": [w,h], "panels": panels,
        "resize_applied": False, "production_enabled": False}


def prepare_comparison(frames, shots, camera_id):
    start = perf_counter()
    png, metadata = build_contact_sheet(frames, shots, camera_id)
    elapsed = perf_counter()-start
    # Encoding and decoding check catches accidental resizing/cropping/recompression.
    with Image.open(io.BytesIO(png)) as sheet:
        fidelity = all(hashlib.sha256(sheet.crop(p["box"]).tobytes()).hexdigest() ==
                       p["decoded_rgb_sha256"] for p in metadata["panels"])
    baseline = [{"type": "input_image", "image_url": "data:image/jpeg;base64," +
                 base64.b64encode(frame).decode()} for frame in frames]
    candidate = [{"type": "input_image", "image_url": "data:image/png;base64," +
                  base64.b64encode(png).decode()}]
    report = dict(metadata, pixel_roundtrip_exact=fidelity,
        source_bytes=sum(map(len, frames)), contact_sheet_bytes=len(png),
        baseline_image_count=3, candidate_image_count=1,
        baseline_requests_per_camera=1, candidate_requests_per_camera=1,
        request_count_savings=0, construction_seconds=round(elapsed, 6),
        model_inference_tested=False, token_savings=None, detection_equivalence=None,
        decision="NOT_APPROVED_FOR_PRODUCTION")
    return baseline, candidate, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path,
                        help="JSON with camera_id and shots (file, shot, timestamp_ct, timing)")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text())
    frames = [(args.manifest.parent / s["file"]).read_bytes() for s in data["shots"]]
    _, _, report = prepare_comparison(frames, data["shots"], data["camera_id"])
    args.report.write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()
