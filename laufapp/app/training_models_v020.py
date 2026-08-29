from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class TrainingPhase(str, Enum):
    FOUNDATION = "foundation"
    BUILD = "build"
    SPECIFIC = "specific"
    RECOVERY = "recovery"
    TAPER = "taper"
    RACE = "race"


class PhysiologicalTarget(str, Enum):
    AEROBIC_BASE = "aerobic_base"
    THRESHOLD = "threshold"
    VO2MAX = "vo2max"
    ECONOMY = "economy"
    MARATHON_SPECIFIC = "marathon_specific"
    AEROBIC_PROGRESSION = "aerobic_progression"
    HILLS = "hills"
    RECOVERY = "recovery"
    RACE = "race"


class WorkoutType(str, Enum):
    EASY = "easy"
    THRESHOLD_INTERVALS = "threshold_intervals"
    CRUISE_INTERVALS = "cruise_intervals"
    TEMPO = "tempo"
    PYRAMID = "pyramid"
    VO2_INTERVALS = "vo2_intervals"
    SHORT_INTERVALS = "short_intervals"
    HILLS = "hills"
    FARTLEK = "fartlek"
    PROGRESSION = "progression"
    MARATHON_PACE = "marathon_pace"
    LONG_EASY = "long_easy"
    LONG_PROGRESSION = "long_progression"
    LONG_MP_BLOCKS = "long_mp_blocks"
    LONG_FAST_FINISH = "long_fast_finish"
    LONG_DELOAD = "long_deload"
    RACE_PREP = "race_prep"
    RACE = "race"


class ReadinessLevel(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


@dataclass(frozen=True)
class TrainingLoad:
    distance_km: float
    duration_min: float
    intensity_zone: str
    low_min: float = 0.0
    moderate_min: float = 0.0
    high_min: float = 0.0
    above_lt1_min: float = 0.0
    around_lt2_min: float = 0.0
    above_lt2_min: float = 0.0
    marathon_pace_min: float = 0.0
    elevation_m: float = 0.0
    long_run_duration_min: float = 0.0
    rpe: float = 3.0
    score: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key, value in list(data.items()):
            if isinstance(value, float):
                data[key] = round(value, 2)
        return data


@dataclass(frozen=True)
class WorkoutVariant:
    key: str
    target: PhysiologicalTarget
    workout_type: WorkoutType
    label: str
    prescription: str
    work_minutes: float
    intensity_zone: str
    work_distance_km: float
    rpe: str
    phase_bias: tuple[TrainingPhase, ...]
    fatigue_cost: float
    pyramid: bool = False


@dataclass(frozen=True)
class RecoveryState:
    level: ReadinessLevel
    score: float
    reasons: tuple[str, ...]
    signals: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "level": self.level.value,
            "score": round(self.score, 2),
            "reasons": list(self.reasons),
            "signals": self.signals,
        }


@dataclass(frozen=True)
class PlannedSession:
    workout_type: str
    title: str
    distance_km: float
    zone_key: str
    rpe: str
    purpose: str
    instructions: str
    target: PhysiologicalTarget
    variant_key: str
    display_kind: str
    load: TrainingLoad
    why: str
    metadata: dict[str, Any]

    def legacy_tuple(self) -> tuple[str, str, float, str, str, str, str]:
        return (
            self.workout_type,
            self.title,
            self.distance_km,
            self.zone_key,
            self.rpe,
            self.purpose,
            self.instructions,
        )


@dataclass(frozen=True)
class LongRunDecision:
    session: PlannedSession
    primary_progression: str
    previous_distance_km: float
    previous_mp_km: float


@dataclass(frozen=True)
class WeeklyPlanDecision:
    sessions: tuple[PlannedSession, ...]
    phase: TrainingPhase
    readiness: RecoveryState
    intensity_distribution: dict[str, float]
    physiological_focus: str
