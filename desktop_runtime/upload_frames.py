from archive_integrity import freeze, VerifiedStore
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3

BASE = Path(r"C:\JubileeCams")
FRAMES = BASE / "frames"
FRAMES, capture_seal = freeze(BASE)
BURST = FRAMES / "burst_latest"
CONFIG = BASE / "r2.json"

STATUS_PATH = FRAMES / "status.json"
VISION_PATH = FRAMES / "vision.json"
BURST_STATUS_PATH = FRAMES / "burst_status.json"

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

s3 = VerifiedStore(s3)

bucket = cfg.get(
    "bucket",
    "jubilee-cameras"
)

public_base = cfg.get(
    "public_base",
    ""
).rstrip("/")

status = json.loads(
    STATUS_PATH.read_text(
        encoding="utf-8-sig"
    )
)

vision = json.loads(
    VISION_PATH.read_text(
        encoding="utf-8-sig"
    )
)

burst_status = json.loads(
    BURST_STATUS_PATH.read_text(
        encoding="utf-8-sig"
    )
)

capture_time = status.get(
    "capture_time_ct"
)

try:
    capture_dt = datetime.fromisoformat(
        capture_time
    )
except Exception:
    capture_dt = datetime.now(
        ZoneInfo("America/Chicago")
    )

archive_prefix = capture_dt.strftime(
    "archive/%Y-%m-%d/%H%M%S"
)

manifest = {
    "capture_time_ct":
        capture_time,

    "dawn_ct":
        status.get("dawn_ct"),

    "window_start_ct":
        status.get("window_start_ct"),

    "window_end_ct":
        status.get("window_end_ct"),

    "archive_prefix":
        archive_prefix,

    "analysis_type":
        vision.get("analysis_type"),

    "analysis_model":
        vision.get("analysis_model"),

    "rubric_version":
        vision.get("rubric_version"),

    "burst_count":
        burst_status.get("burst_count"),

    "target_spacing_seconds":
        burst_status.get(
            "target_spacing_seconds"
        ),

    "cameras": {}
}

#
# 1. Stable latest JPEGs
#
for camera in CAMERAS:

    info = status.get(
        "cameras",
        {}
    ).get(
        camera,
        {}
    )

    if info.get("ok") is not True:
        manifest["cameras"][camera] = {
            "ok": False,
            "error": info.get("error")
        }
        continue

    src = FRAMES / f"{camera}.jpg"

    if not src.exists():
        manifest["cameras"][camera] = {
            "ok": False,
            "error": "latest JPEG missing"
        }
        continue

    latest_key = f"{camera}.jpg"

    s3.upload_file(
        str(src),
        bucket,
        latest_key,
        ExtraArgs={
            "ContentType": "image/jpeg",
            "CacheControl":
                "no-store, max-age=0"
        }
    )

    print(
        f"UPLOADED LATEST: {latest_key}"
    )

    manifest["cameras"][camera] = {
        "ok": True,
        "timestamp_ct":
            info.get("timestamp_ct"),
        "bytes":
            info.get("bytes"),
        "latest_key":
            latest_key,
        "burst": []
    }

#
# 2. Archive all 15 burst images
#
for camera in CAMERAS:

    camera_manifest = (
        manifest["cameras"]
        .get(camera)
    )

    if not camera_manifest:
        continue

    if camera_manifest.get("ok") is not True:
        continue

    burst_info = (
        burst_status.get(
            "cameras",
            {}
        ).get(
            camera,
            {}
        )
    )

    shots = burst_info.get(
        "shots",
        []
    )

    for shot in shots:

        shot_num = shot.get("shot")

        src = (
            BURST /
            f"{camera}_{shot_num}.jpg"
        )

        if not src.exists():
            print(
                f"WARNING burst missing: {src}"
            )
            continue

        archive_key = (
            f"{archive_prefix}/burst/"
            f"{camera}_{shot_num}.jpg"
        )

        s3.upload_file(
            str(src),
            bucket,
            archive_key,
            ExtraArgs={
                "ContentType":
                    "image/jpeg",

                "CacheControl":
                    "public, "
                    "max-age=31536000, "
                    "immutable"
            }
        )

        print(
            f"ARCHIVED BURST: "
            f"{archive_key}"
        )

        camera_manifest[
            "burst"
        ].append({
            "shot":
                shot_num,

            "timestamp_ct":
                shot.get(
                    "timestamp_ct"
                ),

            "timing":
                shot.get("timing"),

            "bytes":
                src.stat().st_size,

            "archive_key":
                archive_key
        })

#
# 3. Publish current machine-readable
#    vision + burst metadata
#
for src_path, key in [
    (VISION_PATH, "vision.json"),
    (
        BURST_STATUS_PATH,
        "burst_status.json"
    ),
]:

    s3.upload_file(
        str(src_path),
        bucket,
        key,
        ExtraArgs={
            "ContentType":
                "application/json",

            "CacheControl":
                "no-store, max-age=0"
        }
    )

    print(
        f"UPLOADED LATEST: {key}"
    )

#
# 4. Archive vision and burst metadata
#
for src_path, filename in [
    (
        VISION_PATH,
        "vision.json"
    ),
    (
        BURST_STATUS_PATH,
        "burst_status.json"
    ),
]:

    archive_key = (
        f"{archive_prefix}/"
        f"{filename}"
    )

    s3.upload_file(
        str(src_path),
        bucket,
        archive_key,
        ExtraArgs={
            "ContentType":
                "application/json",

            "CacheControl":
                "public, "
                "max-age=31536000, "
                "immutable"
        }
    )

    print(
        f"ARCHIVED: {archive_key}"
    )

#
# 5. Archive manifest
#
manifest["capture_id"] = capture_seal["capture_id"]
manifest["sha256"] = dict(s3.hashes)
manifest["local_capture_sha256"] = capture_seal["sha256"]

manifest_bytes = json.dumps(
    manifest,
    indent=2
).encode("utf-8")

manifest_key = (
    f"{archive_prefix}/manifest.json"
)

s3.put_object(
    Bucket=bucket,
    Key=manifest_key,
    Body=manifest_bytes,
    ContentType="application/json",
    CacheControl=(
        "public, "
        "max-age=31536000, "
        "immutable"
    )
)

print(
    f"ARCHIVED: {manifest_key}"
)

#
# 6. Pointer to newest complete archive
#
#
# 7. status.json LAST:
#    indicates complete publication
#
s3.upload_file(
    str(STATUS_PATH),
    bucket,
    "status.json",
    ExtraArgs={
        "ContentType":
            "application/json",

        "CacheControl":
            "no-store, max-age=0"
    }
)

print(
    "UPLOADED: status.json"
)

print()
s3.put_object(
    Bucket=bucket,
    Key="archive/latest_manifest.json",
    Body=manifest_bytes,
    ContentType="application/json",
    CacheControl="no-store, max-age=0"
)

print(
    "UPLOADED: "
    "archive/latest_manifest.json"
)


print(
    "R2 BURST ARCHIVE SUCCESS"
)

print(
    f"ARCHIVE SET: {archive_prefix}"
)

if public_base:
    print()
    print("LATEST:")
    print(
        f"{public_base}/vision.json"
    )
    print(
        f"{public_base}/status.json"
    )
    print()
    print("ARCHIVE MANIFEST:")
    print(
        f"{public_base}/"
        f"{manifest_key}"
    )
