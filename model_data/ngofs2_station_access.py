"""Bounded HTTP access to the original NOAA station NetCDF, never grid substitution."""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

MAX_BYTES = 160 * 1024 * 1024
SOCKET_TIMEOUT_SECONDS = 20
DOWNLOAD_BUDGET_SECONDS = 90


class StationRetrievalError(RuntimeError):
    def __init__(self, attempts):
        self.attempts = attempts
        super().__init__("NOAA station HTTP retrieval unavailable; see retrieval_attempts")


def station_http_urls(cycle, cast):
    if cast not in {"nowcast", "forecast"}:
        raise ValueError("cast must be nowcast or forecast")
    name = f"ngofs2.t{cycle:%H}z.{cycle:%Y%m%d}.stations.{cast}.nc"
    return (
        f"https://noaa-nos-ofs-pds.s3.amazonaws.com/ngofs2/netcdf/{cycle:%Y/%m/%d}/{name}",
        f"https://opendap.co-ops.nos.noaa.gov/thredds/fileServer/NOAA/NGOFS2/MODELS/{cycle:%Y/%m/%d}/{name}",
    )


def download(url, opener=urlopen):
    started = time.monotonic()
    chunks, size = [], 0
    with opener(url, timeout=SOCKET_TIMEOUT_SECONDS) as response:
        length = response.headers.get("Content-Length")
        expected = int(length) if length is not None else None
        if expected is not None and not 0 < expected <= MAX_BYTES:
            raise ValueError("Station NetCDF exceeds bounded size or is empty")
        while True:
            chunk = response.read(min(1024 * 1024, MAX_BYTES + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Station NetCDF exceeds bounded size")
            if time.monotonic() - started > DOWNLOAD_BUDGET_SECONDS:
                raise TimeoutError("Station HTTP download exceeded bounded time")
            chunks.append(chunk)
    payload = b"".join(chunks)
    if expected is not None and size != expected:
        raise ValueError("Truncated station NetCDF download")
    if not (payload.startswith(b"\x89HDF\r\n\x1a\n") or payload[:4] in (b"CDF\x01", b"CDF\x02", b"CDF\x05")):
        raise ValueError("Response is not a NetCDF payload")
    return payload


def validate_station_time(ds, cycle, cast, num2date):
    """Fail closed on a wrong cycle/cast or partial/malformed six-minute series."""
    if str(getattr(ds, "title", "")).strip() != "NGOFS2":
        raise ValueError("Downloaded station file is not identified as NGOFS2")
    tvar = ds.variables["time"]
    times = num2date(tvar[:], units=tvar.units,
                     calendar=getattr(tvar, "calendar", "standard"),
                     only_use_cftime_datetimes=False)
    times = [t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc) for t in times]
    start = cycle - timedelta(hours=6) if cast == "nowcast" else cycle
    count = 61 if cast == "nowcast" else 481
    expected = [start + timedelta(minutes=6 * i) for i in range(count)]
    if times != expected:
        raise ValueError("Station embedded valid times disagree with cycle/cast or six-minute coverage")


def open_latest_station(cast, cycles, dataset_factory, num2date, downloader=download):
    attempts = []
    for cycle in cycles:
        for url in station_http_urls(cycle, cast):
            try:
                payload = downloader(url)
            except HTTPError as exc:
                # Retry absent/unavailable files; authorization and malformed
                # requests remain fatal, as do schema/parser/data failures.
                if exc.code not in {404, 408, 429, 500, 502, 503, 504}:
                    raise
                attempts.append({"url": url, "error_type": "HTTPError", "http_status": exc.code,
                                 "error": str(exc), "stage": "http_download"})
                continue
            except (URLError, TimeoutError) as exc:
                attempts.append({"url": url, "error_type": type(exc).__name__, "error": str(exc),
                                 "stage": "http_download"})
                continue
            # Decode/validation exceptions must not masquerade as a NOAA outage
            # or cause silent selection of an older, apparently valid cycle.
            ds = dataset_factory("ngofs2_station.nc", mode="r", memory=payload)
            try:
                validate_station_time(ds, cycle, cast, num2date)
            except Exception:
                ds.close()
                raise
            receipt = {"method": "HTTPS_FULL_STATION_NETCDF", "source_url": url,
                       "full_file_sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload),
                       "download_completed_at": datetime.now(timezone.utc).isoformat(),
                       "embedded_time_validation": "PASS"}
            return ds, url, cycle, attempts, receipt
    raise StationRetrievalError(attempts)
