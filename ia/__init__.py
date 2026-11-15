"""Internal AI module: two specialists and a synthesis step behind one function call."""

from .backends import describe_engine
from .pipeline import IAError, run_pipeline

__all__ = ["IAError", "describe_engine", "run_pipeline"]
