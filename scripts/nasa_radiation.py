"""Fetch NASA radiation context: python -m scripts.nasa_radiation --help."""

import argparse
import json

from monitoring.nasa_radiation import RadiationUnavailable, fetch_radiation_events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, help="Inclusive UTC date: YYYY-MM-DD")
    parser.add_argument("--end-date", required=True, help="Inclusive UTC date: YYYY-MM-DD")
    args = parser.parse_args()
    try:
        result = fetch_radiation_events(args.start_date, args.end_date)
    except (ValueError, RadiationUnavailable) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
