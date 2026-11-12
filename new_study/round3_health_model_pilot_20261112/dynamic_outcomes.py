"""Incidence-cohort entry point for future disease-state modelling.

No transition or survival parameter is inferred from GBD burden ratios here.
"""
from __future__ import annotations

from dataclasses import dataclass


class TransitionParametersMissing(RuntimeError):
    pass


@dataclass(frozen=True)
class DiseaseTransitions:
    duration_distribution: tuple[float, ...] | None = None
    excess_mortality_by_duration: tuple[float, ...] | None = None
    remission_by_duration: tuple[float, ...] | None = None
    yld_weight_by_duration: tuple[float, ...] | None = None
    life_expectancy_by_death_age: dict[int, float] | None = None


def cohort_outcomes(incident_cases_averted: float, transitions: DiseaseTransitions):
    """Only avoided incident cases may enter; fail closed until full transitions exist."""
    if incident_cases_averted < 0:
        raise ValueError("Avoided incident cases must be nonnegative")
    missing = [name for name, value in vars(transitions).items() if value is None]
    if missing:
        raise TransitionParametersMissing("BLOCKED_DYNAMIC_PARAMETERS: " + ", ".join(missing))
    # Full competing-risk and aging logic requires Work-approved calibration.
    raise TransitionParametersMissing("BLOCKED_DYNAMIC_METHOD: transition interpretation not approved")
