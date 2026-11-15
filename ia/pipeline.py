"""Orchestration: health specialist, space specialist, then the synthesis."""

from .backends import Engine, EngineError, get_engine
from .contracts import DISCLAIMER, as_dict
from .inputs import build_health_input, build_space_input, describe_missing


class IAError(Exception):
    """The engine could not produce a result (missing dependency, model failure, bad configuration)."""


def run_pipeline(analysis: dict, engine: Engine | None = None) -> dict:
    """Run both specialists and the synthesis over a `monitoring.analysis` result."""
    try:
        engine = engine or get_engine()
        health = engine.specialist(build_health_input(analysis))
        space = engine.specialist(build_space_input(analysis))
        summary = engine.synthesize(health, space, describe_missing(analysis))
    except IAError:
        raise
    except EngineError as error:
        raise IAError(str(error)) from error
    except Exception as error:
        # Do not echo model or prompt text: it may contain physiological values.
        raise IAError(f"{type(error).__name__} while running engine {getattr(engine, 'name', '?')}.") from error
    return {
        "engine": engine.name,
        "health": as_dict(health),
        "space": as_dict(space),
        "summary": as_dict(summary),
        "disclaimer": DISCLAIMER,
    }
