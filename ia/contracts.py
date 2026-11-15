"""Plain data contracts between the monolith and the models.

Nothing here carries names, contact data, or free text from a person: inputs are
pseudonymous aggregates computed by `monitoring.analysis`.
"""

from dataclasses import asdict, dataclass, field

CHANGE_FLAGS = frozenset({"shift_up", "shift_down", "rate_up", "counter_decreased"})
MAX_FACTS = 40
MAX_FACT_CHARS = 300
DISCLAIMER = (
    "Resumen generado por modelos de lenguaje a partir de lecturas simuladas o instrumentales. "
    "No es un diagnóstico ni una alerta médica y requiere validación profesional."
)


@dataclass(frozen=True)
class Fact:
    """One statement computed from stored readings. `flag` marks a change worth the models' attention."""

    key: str
    text: str
    flag: str = ""


@dataclass(frozen=True)
class SpecialistInput:
    kind: str  # "health" or "space"
    facts: list[Fact]
    source: str  # "simulated" or "hardware"
    context: dict = field(default_factory=dict)
    # One short sentence counting what changed, computed from the readings (not by a model).
    headline: str = ""

    @property
    def highlights(self) -> list[str]:
        return [f.text for f in self.facts if f.flag in CHANGE_FLAGS]

    def __post_init__(self):
        if len(self.facts) > MAX_FACTS:
            raise ValueError(f"At most {MAX_FACTS} facts per specialist.")
        if any(len(f.text) > MAX_FACT_CHARS for f in self.facts):
            raise ValueError(f"Each fact must be at most {MAX_FACT_CHARS} characters.")


@dataclass(frozen=True)
class SpecialistReport:
    kind: str
    analysis: str
    limitations: list[str]
    engine: str
    # Facts flagged as changes, copied from the input so no engine has to rediscover them in free text.
    highlights: list[str] = field(default_factory=list)
    headline: str = ""


@dataclass(frozen=True)
class Summary:
    findings: list[str]
    uncertainties: list[str]
    missing_data: list[str]
    engine: str
    # Wording written by a language model. Kept apart from `findings`, which are always computed.
    narrative: list[str] = field(default_factory=list)


def as_dict(value) -> dict:
    return asdict(value)
