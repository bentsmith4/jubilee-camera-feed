from camera_lock import serialized
import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

import refresh_all as ra


BASE = Path(r"C:\JubileeCams")
FRAMES = BASE / "frames"
BURST_DIR = FRAMES / "burst_latest"

STATUS_PATH = FRAMES / "status.json"
BURST_STATUS_PATH = FRAMES / "burst_status.json"

BURST_COUNT = 3
BURST_SPACING_SECONDS = 10.0
BURST_SPACING_MS = int(BURST_SPACING_SECONDS * 1000)

# Spread Google/Nest stream requests out a little.
INTER_CAMERA_PAUSE_SECONDS = 5

# If Google rate-limits a stream-generation request,
# wait and retry once rather than losing the camera
# for the entire hourly burst.
DEFAULT_429_WAIT_SECONDS = 30


def safe_error(exc):
    """Never serialize request URLs, command arguments, or auth material."""
    response = getattr(exc, 'response', None)
    code = getattr(response, 'status_code', None)
    return type(exc).__name__ + (': HTTP ' + str(code) if code is not None else ': capture failed; private diagnostics suppressed')


def post_with_429_retry(
    url,
    headers,
    payload,
    timeout=30,
):
    r = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=timeout,
    )

    if r.status_code == 429:
        wait_seconds = DEFAULT_429_WAIT_SECONDS

        retry_after = r.headers.get("Retry-After")

        if retry_after:
            try:
                wait_seconds = max(
                    DEFAULT_429_WAIT_SECONDS,
                    int(retry_after),
                )
            except ValueError:
                pass

        print(
            f"    Google rate limit (429) - "
            f"waiting {wait_seconds}s, "
            f"then retrying once"
        )

        time.sleep(wait_seconds)

        r = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    r.raise_for_status()

    return r


@serialized
def capture_webrtc_burst(
    browser,
    token,
    device,
    slug,
):
    page = browser.new_page(
        viewport={
            "width": 1280,
            "height": 720,
        }
    )

    session = None

    try:
        page.set_content(
            """
<html>
<body style="margin:0;background:black">
  <video id="nestvideo"
         autoplay muted playsinline
         style="width:1280px;height:720px;
                object-fit:contain;background:black">
  </video>
</body>
</html>
"""
        )

        offer = page.evaluate(
            """
async () => {
    const pc = new RTCPeerConnection({
        iceServers: [{
            urls:"stun:stun.l.google.com:19302"
        }]
    });

    window._pc = pc;

    const video =
        document.getElementById("nestvideo");

    const stream = new MediaStream();
    video.srcObject = stream;

    pc.ontrack = (e) => {
        if (e.track.kind === "video") {
            stream.addTrack(e.track);
            video.play().catch(()=>{});
        }
    };

    pc.addTransceiver(
        "audio",
        {direction:"recvonly"}
    );

    pc.addTransceiver(
        "video",
        {direction:"recvonly"}
    );

    pc.createDataChannel("nest");

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);

    if (
        pc.iceGatheringState !== "complete"
    ) {
        await new Promise(resolve => {
            pc.addEventListener(
                "icegatheringstatechange",
                () => {
                    if (
                        pc.iceGatheringState
                        === "complete"
                    ) resolve();
                }
            );
        });
    }

    return pc.localDescription.sdp;
}
"""
        )

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        url = ra.command_url(device)

        r = post_with_429_retry(
            url,
            headers,
            {
                "command":
                    "sdm.devices.commands."
                    "CameraLiveStream."
                    "GenerateWebRtcStream",

                "params": {
                    "offerSdp": offer
                },
            },
        )

        results = r.json()["results"]

        session = results["mediaSessionId"]

        page.evaluate(
            """
async (answer) => {
    await window._pc.setRemoteDescription({
        type:"answer",
        sdp:answer
    });
}
""",
            results["answerSdp"],
        )

        page.wait_for_function(
            """
() => {
    const v =
        document.getElementById(
            "nestvideo"
        );

    return (
        v.videoWidth > 0 &&
        v.videoHeight > 0 &&
        v.readyState >= 2
    );
}
""",
            timeout=45000,
        )

        locator = page.locator("#nestvideo")

        shots = []

        for shot_num in range(
            1,
            BURST_COUNT + 1,
        ):
            outfile = (
                BURST_DIR /
                f"{slug}_{shot_num}.jpg"
            )

            locator.screenshot(
                path=str(outfile),
                type="jpeg",
                quality=90,
            )

            ts = datetime.now(
                ra.TZ
            )

            shots.append({
                "shot": shot_num,
                "timestamp_ct":
                    ts.isoformat(),
                "file":
                    outfile.name,
                "bytes":
                    outfile.stat().st_size,
                "timing":
                    "actual_screenshot_time",
            })

            print(
                f"    shot {shot_num}: "
                f"{ts:%H:%M:%S.%f}"
            )

            if shot_num < BURST_COUNT:
                page.wait_for_timeout(
                    BURST_SPACING_MS
                )

        return shots

    finally:
        if session is not None:
            try:
                headers = {
                    "Authorization":
                        f"Bearer {token}",
                    "Content-Type":
                        "application/json",
                }

                url = ra.command_url(device)

                requests.post(
                    url,
                    headers=headers,
                    json={
                        "command":
                            "sdm.devices.commands."
                            "CameraLiveStream."
                            "StopWebRtcStream",

                        "params": {
                            "mediaSessionId":
                                session
                        },
                    },
                    timeout=15,
                )

            except Exception:
                pass

        try:
            page.close()
        except Exception:
            pass


@serialized
def capture_rtsp_burst(
    token,
    device,
    slug,
):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    url = ra.command_url(device)

    r = post_with_429_retry(
        url,
        headers,
        {
            "command":
                "sdm.devices.commands."
                "CameraLiveStream."
                "GenerateRtspStream",

            "params": {},
        },
    )

    results = r.json()["results"]

    rtsp = (
        results["streamUrls"]["rtspUrl"]
    )

    extension_token = (
        results.get(
            "streamExtensionToken"
        )
    )

    ffmpeg = shutil.which("ffmpeg")

    if not ffmpeg:
        raise RuntimeError(
            "ffmpeg not found"
        )

    # Remove any previous burst images
    # for this camera.
    for old in BURST_DIR.glob(
        f"{slug}_*.jpg"
    ):
        old.unlink()

    pattern = (
        BURST_DIR /
        f"{slug}_%d.jpg"
    )

    print(
        "    sampling one RTSP stream "
        f"every {BURST_SPACING_SECONDS:g} seconds"
    )

    try:
        subprocess.run(
            [
                ffmpeg,
                "-loglevel", "error",
                "-y",

                "-rtsp_transport",
                "tcp",

                "-i",
                rtsp,

                "-vf",
                f"fps=1/{BURST_SPACING_SECONDS:g}",

                "-frames:v",
                str(BURST_COUNT),

                "-q:v",
                "2",

                str(pattern),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
            timeout=60,
        )

    finally:
        # Explicitly stop the Nest RTSP stream
        # when Google supplies an extension token.
        # This reduces leftover active sessions.
        if extension_token:
            try:
                requests.post(
                    url,
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

    files = [
        BURST_DIR /
        f"{slug}_{i}.jpg"
        for i in range(
            1,
            BURST_COUNT + 1
        )
    ]

    for f in files:
        if not f.exists():
            raise RuntimeError(
                f"Missing RTSP burst frame: {f}"
            )

    # FFmpeg samples these from one continuous
    # stream at 1 fps. Wall-clock timestamps are
    # nominal because FFmpeg returns after all
    # three frames have been written.
    end_ts = datetime.now(
        ra.TZ
    )

    shots = []

    for i, outfile in enumerate(
        files,
        start=1,
    ):
        seconds_before_end = (
            (BURST_COUNT - i) * BURST_SPACING_SECONDS
        )

        nominal_ts = (
            end_ts -
            timedelta(
                seconds=seconds_before_end
            )
        )

        shots.append({
            "shot": i,

            "timestamp_ct":
                nominal_ts.isoformat(),

            "file":
                outfile.name,

            "bytes":
                outfile.stat().st_size,

            "timing":
                "nominal_interval_single_stream",
        })

        print(
            f"    shot {i}: "
            f"~{nominal_ts:%H:%M:%S}"
        )

    return shots


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--force",
        action="store_true",
    )

    args = parser.parse_args()

    FRAMES.mkdir(
        parents=True,
        exist_ok=True,
    )

    BURST_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Remove stale burst images.
    for old in BURST_DIR.glob(
        "*.jpg"
    ):
        old.unlink()

    now, dawn, start, end = (
        ra.dawn_window()
    )

    if (
        not args.force
        and not (
            start <= now <= end
        )
    ):
        print(
            f"Outside camera window. "
            f"Dawn={dawn:%H:%M}; "
            f"window="
            f"{start:%H:%M}-"
            f"{end:%H:%M} CT"
        )

        return

    creds = ra.load_credentials()

    token = (
        ra.refresh_access_token(
            creds
        )
    )

    devices = ra.list_devices(
        token
    )

    status = {
        "capture_time_ct":
            now.isoformat(),

        "dawn_ct":
            dawn.isoformat(),

        "window_start_ct":
            start.isoformat(),

        "window_end_ct":
            end.isoformat(),

        "burst_count":
            BURST_COUNT,

        "burst_spacing_seconds":
            BURST_SPACING_SECONDS,

        "cameras": {},
    }

    burst_status = {
        "capture_time_ct":
            now.isoformat(),

        "dawn_ct":
            dawn.isoformat(),

        "burst_count":
            BURST_COUNT,

        "target_spacing_seconds":
            BURST_SPACING_SECONDS,

        "cameras": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
        )

        try:
            for device in devices:
                name = ra.custom_name(
                    device
                )

                if (
                    name
                    not in
                    ra.CAMERA_NAMES
                ):
                    continue

                slug = (
                    ra.CAMERA_NAMES[
                        name
                    ]
                )

                proto = ra.protocols(
                    device
                )

                print()
                print(
                    f"Capturing burst: "
                    f"{slug} "
                    f"({','.join(proto)})"
                )

                try:
                    if "WEB_RTC" in proto:
                        shots = (
                            capture_webrtc_burst(
                                browser,
                                token,
                                device,
                                slug,
                            )
                        )

                    elif "RTSP" in proto:
                        shots = (
                            capture_rtsp_burst(
                                token,
                                device,
                                slug,
                            )
                        )

                    else:
                        raise RuntimeError(
                            "Unsupported "
                            f"protocols: {proto}"
                        )

                    # Shot 3 becomes normal
                    # latest image.
                    latest_source = (
                        BURST_DIR /
                        f"{slug}_3.jpg"
                    )

                    latest_dest = (
                        FRAMES /
                        f"{slug}.jpg"
                    )

                    shutil.copy2(
                        latest_source,
                        latest_dest,
                    )

                    last_shot = shots[-1]

                    status[
                        "cameras"
                    ][slug] = {
                        "ok": True,

                        "timestamp_ct":
                            last_shot[
                                "timestamp_ct"
                            ],

                        "bytes":
                            latest_dest
                            .stat()
                            .st_size,

                        "burst_count":
                            BURST_COUNT,
                    }

                    burst_status[
                        "cameras"
                    ][slug] = {
                        "ok": True,
                        "protocols": proto,
                        "shots": shots,
                    }

                    print(
                        f"  OK latest: "
                        f"{latest_dest}"
                    )

                except Exception as e:
                    ts = datetime.now(
                        ra.TZ
                    ).isoformat()

                    status[
                        "cameras"
                    ][slug] = {
                        "ok": False,
                        "timestamp_ct": ts,
                        "error": safe_error(e),
                    }

                    burst_status[
                        "cameras"
                    ][slug] = {
                        "ok": False,
                        "error": safe_error(e),
                    }

                    print(
                        f"  FAILED: {safe_error(e)}"
                    )

                # Avoid immediately opening the next
                # Google/Nest stream session.
                time.sleep(
                    INTER_CAMERA_PAUSE_SECONDS
                )

        finally:
            browser.close()

    for slug in set(ra.CAMERA_NAMES.values()):
        status["cameras"].setdefault(slug, {"ok": False, "error": "device_not_in_permitted_inventory"})
        burst_status["cameras"].setdefault(slug, {"ok": False, "error": "device_not_in_permitted_inventory"})

    STATUS_PATH.write_text(
        json.dumps(
            status,
            indent=2,
        ),
        encoding="utf-8",
    )

    BURST_STATUS_PATH.write_text(
        json.dumps(
            burst_status,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        f"WROTE: {STATUS_PATH}"
    )

    print(
        f"WROTE: {BURST_STATUS_PATH}"
    )

    print()
    print(
        "TRUE 3-FRAME BURST "
        "CAPTURE COMPLETE"
    )


if __name__ == "__main__":
    main()
