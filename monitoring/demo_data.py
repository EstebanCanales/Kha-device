"""Synthetic readings for the Kha-device 01 demo profiles.

Pure Python, no Django: both `scripts/simulate_kha.py` (over HTTP) and `manage.py demo_kha`
(straight into the database) build their packets from this, so they produce the same data.
Every value is invented.
"""

import random
from datetime import datetime, timedelta

VITALS = "kha-vitals-sim-001"
CAD = "cad-sim-001"


def reading(sensor_id, metric, value, unit, **extra):
    quality = "missing" if value is None else "valid"
    return {"sensor_id": sensor_id, "metric": metric, "value": value, "unit": unit, "quality": quality, **extra}


# Simulated devices report one sample every 30 minutes. It is a simulation choice, not a confirmed hardware rate.
STEP_SECONDS = 1800
# Default history: 24 hours, which gives 48 samples, enough for a baseline and a recent window (the analysis needs 20).
DEFAULT_MINUTES = 1440


def generate(
    start: datetime, samples: int, step_seconds: int, seed: int, scenario: str, dropout: float,
    epoch_high: str, epoch_low: str,
) -> list[tuple[datetime, list[dict], list[dict]]]:
    """One (time, vital-signs readings, dosimeter readings) per sample.

    `stress` shifts the last 30% of the window away from the early baseline so the analysis has
    something to report; `baseline` keeps everything steady.
    """
    rng = random.Random(seed)
    shift_from = int(samples * 0.7)
    dose = 0.21  # mGy already accumulated at the start of the window
    dose_low = dose
    out = []
    for n in range(samples):
        at = start + timedelta(seconds=n * step_seconds)
        stressed = scenario == "stress" and n >= shift_from
        hr = 68 + rng.gauss(0, 1.8) + (22 if stressed else 0)
        spo2 = min(100.0, 97.5 + rng.gauss(0, 0.4) - (3.0 if stressed else 0))
        resp = 14 + rng.gauss(0, 0.6) + (6 if stressed else 0)
        skin = 33.1 + rng.gauss(0, 0.08) + (0.9 if stressed else 0)
        rate = 0.02 * (6 if stressed else 1) * (1 + rng.gauss(0, 0.1))  # mGy/h
        dose += max(rate, 0) * step_seconds / 3600
        # The low-resolution chamber reports in coarser steps (simulated resolution).
        dose_low = max(dose_low, round(dose, 2))
        hr_value = None if rng.random() < dropout else f"{hr:.1f}"
        vitals = [
            reading("max86178-ppg-001", "heart_rate", hr_value, "bpm"),
            reading("max86178-ppg-001", "pulse_rate", f"{hr + rng.gauss(0, 0.4):.1f}", "bpm"),
            reading("max86178-ppg-001", "spo2", f"{spo2:.1f}", "%"),
            reading("max86178-ppg-001", "respiratory_rate", f"{resp:.1f}", "breaths/min",
                    method="ppg_modulation_simulated", method_version="sim.v1"),
            reading("max30205-001", "skin_temperature", f"{skin:.2f}", "degC"),
        ]
        cad = [
            reading("cad-dis-high-001", "absorbed_dose_cumulative", f"{dose:.6f}", "mGy", counter_epoch=epoch_high),
            reading("cad-dis-low-001", "absorbed_dose_cumulative", f"{dose_low:.2f}", "mGy", counter_epoch=epoch_low),
            reading("cad-exposure-001", "exposure_duration", str(n * step_seconds), "s"),
            reading("cad-tmp117-001", "internal_temperature", f"{24.5 + rng.gauss(0, 0.05):.2f}", "degC"),
        ]
        out.append((at, vitals, cad))
    return out
