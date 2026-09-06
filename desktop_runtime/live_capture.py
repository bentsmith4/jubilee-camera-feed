from camera_lock import serialized
import json
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime

import requests
from playwright.sync_api import sync_playwright

import refresh_all as ra
import burst_capture as bc

BASE = Path(r"C:\JubileeCams")
LIVE = BASE / "live_frames"
LIVE_BURST = LIVE / "burst_latest"

LIVE.mkdir(parents=True, exist_ok=True)
LIVE_BURST.mkdir(parents=True, exist_ok=True)

# Reuse the proven WebRTC engine for one frame.
bc.BURST_DIR = LIVE_BURST
bc.BURST_COUNT = 1
bc.BURST_SPACING_MS = 0


@serialized
def capture_rtsp_live(token, device, slug):
    """
    Generate ONE RTSP stream, grab ONE frame,
    then explicitly stop/revoke that Nest stream.
    """

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    command_url = ra.command_url(device)

    extension_token = None

    try:
        r = requests.post(
            command_url,
            headers=headers,
            json={
                "command":
                    "sdm.devices.commands."
                    "CameraLiveStream."
                    "GenerateRtspStream",
                "params": {},
            },
            timeout=30,
        )

        r.raise_for_status()

        results = r.json()["results"]

        rtsp_url = (
            results["streamUrls"]["rtspUrl"]
        )

        extension_token = (
            results.get("streamExtensionToken")
        )

        ffmpeg = shutil.which("ffmpeg")

        if not ffmpeg:
            raise RuntimeError(
                "ffmpeg not found"
            )

        outfile = (
            LIVE_BURST /
            f"{slug}_1.jpg"
        )

        if outfile.exists():
            outfile.unlink()

        try:
            subprocess.run(
                [
                    ffmpeg,
                    "-loglevel", "error",
                    "-y",
                    "-rtsp_transport", "tcp",
                    "-i", rtsp_url,
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(outfile),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
                timeout=45,
            )

        except subprocess.CalledProcessError:
            # Deliberately do NOT include the command
            # because it contains a temporary signed URL.
            raise RuntimeError(
                "RTSP ffmpeg capture failed"
            )

        if not outfile.exists():
            raise RuntimeError(
                "RTSP frame was not created"
            )

        ts = datetime.now(ra.TZ)

        return [{
            "shot": 1,
            "timestamp_ct": ts.isoformat(),
            "file": outfile.name,
            "bytes": outfile.stat().st_size,
            "timing": "single_rtsp_frame",
        }]

    finally:
        # Google recommends stopping/revoking an
        # RTSP live stream when finished.
        if extension_token:
            try:
                requests.post(
                    command_url,
                    headers=headers,
                    json={
                        "command":
                            "sdm.devices.commands."
                            "CameraLiveStream."
                            "StopRtspStream",
                        "params": {
                            "streamExtensionToken":
                                extension_token
                        },
                    },
                    timeout=15,
                )

            except Exception:
                pass


# Remove old temporary frames.
for old in LIVE_BURST.glob("*.jpg"):
    old.unlink()


now, dawn, start, end = ra.dawn_window()

creds = ra.load_credentials()
token = ra.refresh_access_token(creds)
devices = ra.list_devices(token)

status = {
    "capture_time_ct": now.isoformat(),
    "mode": "near_live_single_frame",
    "cameras": {},
}


with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=True
    )

    try:
        for device in devices:
            name = ra.custom_name(device)

            if name not in ra.CAMERA_NAMES:
                continue

            slug = ra.CAMERA_NAMES[name]
            proto = ra.protocols(device)

            print()
            print(
                f"Live capture: {slug} "
                f"({','.join(proto)})"
            )

            try:
                if "WEB_RTC" in proto:

                    shots = (
                        bc.capture_webrtc_burst(
                            browser,
                            token,
                            device,
                            slug
                        )
                    )

                elif "RTSP" in proto:

                    last_error = None
                    shots = None

                    for attempt in range(1, 4):
                        try:
                            print(
                                f"    RTSP attempt "
                                f"{attempt}/3"
                            )

                            shots = capture_rtsp_live(
                                token,
                                device,
                                slug
                            )

                            last_error = None
                            break

                        except Exception as e:
                            last_error = e

                            print(
                                f"    RTSP attempt "
                                f"{attempt} failed"
                            )

                            if attempt < 3:
                                time.sleep(2)

                    if last_error is not None:
                        raise last_error

                else:
                    raise RuntimeError(
                        f"Unsupported protocols: "
                        f"{proto}"
                    )

                if not shots:
                    raise RuntimeError(
                        "Camera returned no frame"
                    )

                last_shot = shots[-1]

                source = (
                    LIVE_BURST /
                    last_shot["file"]
                )

                dest = (
                    LIVE /
                    f"{slug}.jpg"
                )

                shutil.copy2(
                    source,
                    dest
                )

                status[
                    "cameras"
                ][slug] = {
                    "ok": True,
                    "timestamp_ct":
                        last_shot[
                            "timestamp_ct"
                        ],
                    "bytes":
                        dest.stat().st_size,
                    "protocols": proto,
                }

                print(
                    f"  LIVE OK: {dest}"
                )

            except Exception as e:

                status[
                    "cameras"
                ][slug] = {
                    "ok": False,
                    "error": bc.safe_error(e),
                }

                print(
                    f"  LIVE FAILED: {bc.safe_error(e)}"
                )

    finally:
        browser.close()


for slug in set(ra.CAMERA_NAMES.values()):
    status["cameras"].setdefault(slug, {"ok": False, "error": "device_not_in_permitted_inventory"})

status_path = LIVE / "status.json"

status_path.write_text(
    json.dumps(
        status,
        indent=2
    ),
    encoding="utf-8"
)

successes = sum(
    1
    for camera
    in status["cameras"].values()
    if camera.get("ok")
)

print()
print("=" * 60)
print("NEAR-LIVE CAPTURE COMPLETE")
print(
    f"Cameras successful: "
    f"{successes}/5"
)
print("=" * 60)
