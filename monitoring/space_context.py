"""NASA DONKI radiation-belt events as environmental context for the space specialist.

This is context, never personal dose: the events say what the space environment did around the
analysed window, not what any person absorbed. It is optional (it needs a NASA key), cached, and
it never raises: when it cannot be had, the summary simply goes without it.
"""

from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.cache import cache

from .nasa_radiation import RadiationUnavailable, fetch_radiation_events

CONTEXT_DAYS = 7  # the week up to the last reading
MAX_EVENT_TIMES = 10
CACHE_SECONDS = 900  # the same window and key the /radiation-context/ endpoint uses


def space_weather(analysis: dict) -> dict:
    """A small, prompt-sized description of the NASA events around the analysed window."""
    key = settings.RADATION_API_KEY
    last = analysis["window"]["last_observed_at"]
    if not key:
        return {"status": "not_configured"}
    if not last:
        return {"status": "no_window"}
    end = datetime.fromisoformat(last).astimezone(timezone.utc).date()
    start = end - timedelta(days=CONTEXT_DAYS - 1)
    start_date, end_date = start.isoformat(), end.isoformat()
    cache_key = f"nasa-rbe:{start_date}:{end_date}"
    result = cache.get(cache_key)
    if result is None:
        try:
            result = fetch_radiation_events(start_date, end_date, api_key=key)
        except (RadiationUnavailable, ValueError):
            return {"status": "unavailable", "start_date": start_date, "end_date": end_date}
        cache.set(cache_key, result, timeout=CACHE_SECONDS)
    return {
        "status": "ok",
        "source": "nasa_donki",
        "start_date": start_date,
        "end_date": end_date,
        "event_count": result["event_count"],
        "event_times": [e["eventTime"] for e in result["events"][:MAX_EVENT_TIMES]],
        "personal_dose_available": False,
    }
