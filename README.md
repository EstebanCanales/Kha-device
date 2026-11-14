# Kha-device

## Add synthetic test data in Django Admin

Install the locked dependencies with `uv sync`, then run:

```bash
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Sign in at `http://127.0.0.1:8000/admin/`. All models in `monitoring` are
available there. Create configuration records in this order: participant,
session, device, sensor, sensor capability, and session device assignment.
Create a counter epoch before a cumulative dose measurement. Packets,
measurements, ECG samples, and analysis results can be added for synthetic
tests, but saved records cannot be edited or deleted through Admin.

Use `simulated` as the source for demonstration devices and packets. The
Admin forms validate model relationships and units; these records do not
represent a verified hardware integration.
