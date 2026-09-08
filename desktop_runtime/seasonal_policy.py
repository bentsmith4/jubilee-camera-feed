"""Owner's conservative Mobile Bay seasonal window; see model_data/seasonal_policy.json."""
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Chicago")
START = (5, 18)
END = (11, 14)

def in_season(now=None):
    if now is None:
        now = datetime.now(TZ)
    if now.tzinfo is None:
        raise ValueError("Season checks require a timezone-aware datetime")
    local = now.astimezone(TZ)
    return START <= (local.month, local.day) <= END

def require_season():
    if not in_season():
        print("Jubilee seasonal pause: not monitored (May 18–November 14 only).")
        raise SystemExit(0)
