from publish_github import validate_private
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

BASE = Path(r"C:\JubileeCams")
LIVE = BASE / "live_frames"
CONFIG = BASE / "r2.json"

from camera_policy import CAMERA_IDS as CAMERAS

cfg = json.loads(
    CONFIG.read_text(encoding="utf-8-sig")
)

s3 = boto3.client(
    "s3",
    endpoint_url=cfg["endpoint"].rstrip("/"),
    aws_access_key_id=cfg["access_key"],
    aws_secret_access_key=cfg["secret_key"],
    region_name="auto",
)

bucket = cfg.get("bucket", "jubilee-cameras")

status_path = LIVE / "status.json"

capture_status = json.loads(
    status_path.read_text(encoding="utf-8-sig")
)

validate_private(capture_status)

published = {}
fresh_count = 0

for camera in CAMERAS:
    camera_status = (
        capture_status
        .get("cameras", {})
        .get(camera, {})
    )

    # Critical rule:
    # Never republish an old JPEG when this cycle failed.
    if camera_status.get("ok") is not True:
        published[camera] = {
            "ok": False,
            "timestamp_ct":
                camera_status.get("timestamp_ct"),
            "error":
                camera_status.get(
                    "error",
                    "fresh_capture_failed"
                ),
        }

        print(f"NOT FRESH - SKIPPED: {camera}")
        continue

    try:
        captured = datetime.fromisoformat(camera_status['timestamp_ct'])
        age = (datetime.now(ZoneInfo('America/Chicago')) - captured).total_seconds()
        if not -120 <= age <= 600:
            raise ValueError('stale_or_future')
    except (KeyError, TypeError, ValueError):
        published[camera] = {'ok': False, 'error': 'stale_future_or_invalid_timestamp'}
        continue
    src = LIVE / f"{camera}.jpg"

    if not src.exists():
        published[camera] = {
            "ok": False,
            "timestamp_ct":
                camera_status.get("timestamp_ct"),
            "error": "fresh_image_missing",
        }

        print(f"MISSING - SKIPPED: {camera}")
        continue

    key = f"live/{camera}.jpg"

    s3.upload_file(
        str(src),
        bucket,
        key,
        ExtraArgs={
            "ContentType": "image/jpeg",
            "CacheControl": "no-store, max-age=0",
        },
    )

    published[camera] = {
        "ok": True,
        "timestamp_ct":
            camera_status.get("timestamp_ct"),
        "bytes": src.stat().st_size,
        "key": key,
    }

    fresh_count += 1

    print(f"FRESH LIVE UPLOADED: {camera}")


now = datetime.now(
    ZoneInfo("America/Chicago")
)

live_status = {
    "updated_ct": now.isoformat(),
    "capture_time_ct":
        capture_status.get("capture_time_ct"),
    "refresh_target_seconds": 180,
    "fresh_camera_count": fresh_count,
    "camera_count": len(CAMERAS),
    "cameras": published,
}

live_status_path = LIVE / "live_status.json"

live_status_path.write_text(
    json.dumps(live_status, indent=2),
    encoding="utf-8",
)

s3.upload_file(
    str(live_status_path),
    bucket,
    "live/live_status.json",
    ExtraArgs={
        "ContentType": "application/json",
        "CacheControl": "no-store, max-age=0",
    },
)

print()
print("LIVE CAMERA PUBLICATION COMPLETE")
print(f"Fresh cameras published: {fresh_count}/{len(CAMERAS)}")
print(f"Updated: {now:%Y-%m-%d %I:%M:%S %p} CT")
