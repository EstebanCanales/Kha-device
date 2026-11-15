"""Compare model choices on fixed synthetic cases, with checks that need no human reading.

    uv run python -m ia.evaluation                                  # the default set of combinations
    uv run python -m ia.evaluation --config mine=llama3.2:3b,llama3.2:3b,granite3.3:2b
    uv run python -m ia.evaluation --only kha --cases stress -v      # one combination, one case, details

Each combination is "health,space,synthesis" Ollama model names. The checks catch the failures seen
so far: invented or misplaced figures, medical interpretation, broken Spanish, replies that are not
the requested JSON, and changes the model never mentions. They do not judge medical correctness:
that still needs a person. Needs `ollama serve` and the models installed.
"""

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field

from .backends import (
    OllamaEngine,
    _flawed_change,
    _json_object,
    _pick,
    _unsupported_numbers,
    reply_analysis,
    reply_findings,
)
from .inputs import build_health_input, build_space_input, describe_missing

# Words that turn "this value changed" into "this means something". Matched on the analysis text only.
INTERPRETATION = re.compile(
    r"estr[eé]s|ansiedad|enfermedad|infecci[oó]n|riesgo|peligro|grave|preocupante|alarmante|"
    r"tratamiento|medicaci[oó]n|s[ií]ntoma|deshidrata|fiebre|hipoxia|taquicardia|hiperventila|"
    r"respuesta (?:del|al) (?:cuerpo|organismo)|indica(?:n)? (?:que|un|una)|debido a|se debe|causad[oa]",
    re.IGNORECASE,
)
# A consonant right before "ñ" or accented vowels Spanish does not use: signs of garbled accents.
BROKEN_SPANISH = re.compile(r"[bcdfghjklmnpqrstvwxyz]ñ|[àèìòùâêîôû]", re.IGNORECASE)
DEFAULT_CONFIGS = {
    "kha (los tres de README)": ("kha-health", "kha-astronomy", "granite3.3:2b"),
    "llama3.2:3b en los tres": ("llama3.2:3b", "llama3.2:3b", "llama3.2:3b"),
    "llama3.2:3b + granite": ("llama3.2:3b", "llama3.2:3b", "granite3.3:2b"),
    "gemma3:4b en los tres": ("gemma3:4b", "gemma3:4b", "gemma3:4b"),
}


def metric(status, unit, base, recent, z, readings=40):
    return {"status": status, "unit": unit, "z_score": z, "readings": readings,
            "baseline": {"median": base}, "recent": {"median": recent}}


def make_case(name: str) -> dict:
    """Analyses shaped like `monitoring.analysis.analyze_session`, for three situations."""
    stable = {
        "heart_rate": metric("stable", "bpm", 68.1, 68.9, 0.4), "spo2": metric("stable", "%", 97.4, 97.3, -0.2),
        "respiratory_rate": metric("stable", "breaths/min", 13.9, 14.0, 0.1),
        "skin_temperature": metric("stable", "degC", 33.1, 33.12, 0.1),
    }
    chamber = {"sensor": "cad-dis-high-001", "channel": "dis_high", "unit": "mGy", "latest_value": 0.26,
               "counter_decreased": False, "status": "stable", "readings": 120,
               "rate_per_hour": {"early": 0.02, "recent": 0.021}, "rate_ratio": 1.05}
    base = {"session": "s", "source": "simulated", "participant": "synthetic", "gravity_context": "unknown",
            "metrics": stable, "dose": {"chambers": [chamber]}, "missing_data": []}
    if name == "stress":
        base["metrics"] = {
            "heart_rate": metric("shift_up", "bpm", 68.1, 89.15, 10.53), "spo2": metric("shift_down", "%", 97.4, 94.4, -6.0),
            "respiratory_rate": metric("shift_up", "breaths/min", 13.9, 20.1, 6.2),
            "skin_temperature": metric("shift_up", "degC", 33.095, 34.065, 6.47),
        }
        base["dose"] = {"chambers": [
            {**chamber, "latest_value": 0.260045, "status": "rate_up", "rate_ratio": 5.83,
             "rate_per_hour": {"early": 0.02028, "recent": 0.118256}},
            {**chamber, "sensor": "cad-dis-low-001", "channel": "dis_low", "latest_value": 0.26, "status": "rate_up",
             "rate_ratio": 5.53, "rate_per_hour": {"early": 0.025532, "recent": 0.141176}},
        ]}
        base["missing_data"] = [{"code": "missing_readings", "metric": "heart_rate", "count": 2}]
    elif name == "sparse":
        base["metrics"] = {
            "heart_rate": metric("insufficient_data", "bpm", 0, 0, 0, readings=6), "spo2": {"status": "no_data"},
            "respiratory_rate": {"status": "no_data"}, "skin_temperature": metric("stable", "degC", 33.1, 33.15, 0.3),
        }
        base["dose"] = {"chambers": []}
        base["missing_data"] = [{"code": "no_valid_readings", "metric": "spo2"}, {"code": "no_dose_readings", "metric": "x"}]
    elif name != "quiet":
        raise ValueError(name)
    return base


@dataclass
class Score:
    checks: dict[str, bool] = field(default_factory=dict)
    seconds: float = 0.0
    notes: list[str] = field(default_factory=list)


class Recording(OllamaEngine):
    """The real Ollama engine, remembering every raw reply and how long it took."""

    def __init__(self, models: tuple[str, str, str]):
        super().__init__()
        self.models = dict(zip(("health", "space", "synthesis"), models, strict=True))
        self.calls: list[tuple[str, str, float]] = []

    def _generate(self, role, user):
        started = time.perf_counter()
        reply = super()._generate(role, user)
        self.calls.append((role, reply, time.perf_counter() - started))
        return reply


def score_specialist(reply: str, facts_text: str, highlights: list[str]) -> dict[str, bool]:
    """Scores what the model wrote, not what the engine finally showed (it may have discarded it)."""
    parsed = _json_object(reply)
    text = reply_analysis(reply)
    changed_numbers = [re.findall(r"\d+(?:[.,]\d+)?", h)[-2:] for h in highlights]
    return {
        "json": bool(parsed) and bool(text),
        "sin_interpretar": not INTERPRETATION.search(text),
        "cifras_reales": not _unsupported_numbers(text, facts_text),
        "sin_cambio_falso": not _flawed_change(text),
        "español_limpio": not BROKEN_SPANISH.search(text),
        # Every flagged change should show at least its latest figure.
        "menciona_cambios": all(any(n.replace(",", ".") in text.replace(",", ".") for n in pair) for pair in changed_numbers) if changed_numbers else True,
    }


def score_synthesis(reply: str, reports_text: str) -> dict[str, bool]:
    parsed = _json_object(reply)
    text = " ".join(reply_findings(reply)) if parsed else ""
    return {
        "json": bool(parsed) and bool(_pick(parsed, "findings")),
        "sin_interpretar": not INTERPRETATION.search(text),
        "cifras_reales": not _unsupported_numbers(text, reports_text),
        "sin_cambio_falso": not _flawed_change(text),
        "español_limpio": not BROKEN_SPANISH.search(text),
        "menciona_cambios": True,
    }


def run_case(models: tuple[str, str, str], case: str) -> list[Score]:
    analysis = make_case(case)
    engine = Recording(models)
    health_in, space_in = build_health_input(analysis), build_space_input(analysis)
    health, space = engine.specialist(health_in), engine.specialist(space_in)
    engine.synthesize(health, space, describe_missing(analysis))
    (_, h_reply, h_t), (_, s_reply, s_t), (_, y_reply, y_t) = engine.calls
    facts = lambda data: " ".join(f.text for f in data.facts)  # noqa: E731
    scores = []
    for kind, reply, seconds, checks, text in (
        ("salud", h_reply, h_t, score_specialist(h_reply, facts(health_in), health.highlights), reply_analysis(h_reply)),
        ("astronomía", s_reply, s_t, score_specialist(s_reply, facts(space_in), space.highlights), reply_analysis(s_reply)),
        ("síntesis", y_reply, y_t, score_synthesis(y_reply, f"{health.analysis} {space.analysis} {health.headline} {space.headline}"), " ".join(reply_findings(y_reply))),
    ):
        scores.append(Score(checks, seconds, [f"{kind}: {text[:230]}"] if not all(checks.values()) else []))
        scores[-1].notes.extend(f"  falla {k}" for k, ok in checks.items() if not ok)
    return scores


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", action="append", metavar="NOMBRE=SALUD,ESPACIO,SINTESIS")
    parser.add_argument("--only", help="Run only combinations whose name contains this text")
    parser.add_argument("--cases", default="stress,quiet,sparse")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show the text of every failed check")
    args = parser.parse_args(argv)

    configs = dict(DEFAULT_CONFIGS)
    if args.config:
        configs = {}
        for item in args.config:
            name, _, models = item.partition("=")
            parts = tuple(m.strip() for m in models.split(","))
            if len(parts) != 3:
                parser.error("--config needs NOMBRE=SALUD,ESPACIO,SINTESIS")
            configs[name] = parts
    if args.only:
        configs = {k: v for k, v in configs.items() if args.only in k}
    cases = args.cases.split(",")

    columns = ["json", "sin_interpretar", "cifras_reales", "sin_cambio_falso", "español_limpio", "menciona_cambios"]
    rows, details = [], []
    for name, models in configs.items():
        print(f"… {name}: {', '.join(models)}", file=sys.stderr, flush=True)
        totals = {c: [0, 0] for c in columns}
        seconds = []
        try:
            for case in cases:
                for score in run_case(models, case):
                    seconds.append(score.seconds)
                    for c, ok in score.checks.items():
                        totals[c][0] += ok
                        totals[c][1] += 1
                    details.extend(f"[{name} / {case}] {n}" for n in score.notes)
        except Exception as error:  # a missing model or a stopped server must not hide the other results
            print(f"   no se pudo evaluar «{name}»: {error}", file=sys.stderr)
            continue
        rows.append((name, totals, sum(seconds) / len(seconds), sum(seconds)))

    head = "| combinación | " + " | ".join(columns) + " | s/llamada |"
    print(head + "\n|" + "---|" * (len(columns) + 2))
    for name, totals, mean, _ in rows:
        cells = " | ".join(f"{totals[c][0]}/{totals[c][1]}" for c in columns)
        print(f"| {name} | {cells} | {mean:.1f} |")
    if args.verbose:
        print("\n" + "\n".join(details))
    print(json.dumps({"cases": cases, "note": "Automatic checks only; medical correctness needs a person."}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
