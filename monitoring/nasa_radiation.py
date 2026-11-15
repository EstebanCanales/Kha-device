"""NASA DONKI environmental events, separate from personal dosimetry."""

import json
import os
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ENDPOINT = "https://api.nasa.gov/DONKI/RBE"
MAX_BYTES = 2 * 1024 * 1024
MAX_EVENTS = 1000


class RadiationUnavailable(Exception):
    """Safe error text: never include the upstream URL containing the API key."""


def validate_window(start_date, end_date):
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError):
        raise ValueError("Use YYYY-MM-DD dates.") from None
    if start.isoformat() != start_date or end.isoformat() != end_date:
        raise ValueError("Use YYYY-MM-DD dates.")
    if not timedelta(0) <= end - start < timedelta(days=31):
        raise ValueError("Date range must be ordered and at most 31 inclusive days.")
    return start, end


def fetch_radiation_events(start_date, end_date, *, api_key=None):
    start, end = validate_window(start_date, end_date)
    key = api_key if api_key is not None else (os.getenv("RADATION_API_KEY") or os.getenv("RADIATION_API_KEY", ""))
    if not key.strip():
        raise RadiationUnavailable("RADATION_API_KEY is not configured.")
    query = urlencode({"startDate": start_date, "endDate": end_date, "api_key": key})
    request = Request(f"{ENDPOINT}?{query}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=15) as response:
            body = response.read(MAX_BYTES + 1)
    except HTTPError as error:
        code = error.code
        error.close()
        raise RadiationUnavailable(f"NASA DONKI request failed (HTTP {code}).") from None
    except (URLError, OSError, ValueError):
        raise RadiationUnavailable("NASA DONKI could not be reached.") from None
    if len(body) > MAX_BYTES:
        raise RadiationUnavailable("NASA DONKI response exceeds the size limit.")
    try:
        events = json.loads(body)
        # DONKI may return JSON null when the search has no events.
        if events is None:
            events = []
        if not isinstance(events, list) or len(events) > MAX_EVENTS:
            raise ValueError
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get("rbeID"), str) or not event["rbeID"]:
                raise ValueError
            instant = datetime.fromisoformat(event["eventTime"].replace("Z", "+00:00"))
            if instant.utcoffset() is None or not start <= instant.astimezone(timezone.utc).date() <= end:
                raise ValueError
        events.sort(key=lambda item: (item["eventTime"], item["rbeID"]))
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        raise RadiationUnavailable("NASA DONKI returned an invalid event response.") from None
    return {
        "schema_version": "nasa-radiation-context.v1",
        "source": "nasa_donki", "event_type": "RBE", "source_url": ENDPOINT,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "start_date": start_date, "end_date": end_date,
        "personal_dose_available": False, "event_count": len(events), "events": events,
        "note": "Environmental event context only; no personal dose, dose rate, or astronaut exposure is inferred. An empty list does not mean zero radiation.",
    }
