import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import IntEnum


class FSRSRating(IntEnum):
    AGAIN = 1
    HARD = 2
    GOOD = 3
    EASY = 4


@dataclass(frozen=True)
class FSRSState:
    difficulty: float = 5.0
    stability_days: float = 1.0
    last_review_at: datetime | None = None
    next_review_at: datetime | None = None
    review_count: int = 0


@dataclass(frozen=True)
class FSRSSchedule:
    rating: FSRSRating
    difficulty: float
    stability_days: float
    retrievability: float
    last_review_at: datetime
    next_review_at: datetime
    review_count: int
    model_version: str = "fsrs-dsr-v1"


def retrievability(state: FSRSState, now: datetime) -> float:
    if state.last_review_at is None:
        return 0.0
    elapsed_days = max(0.0, (now - state.last_review_at).total_seconds() / 86400.0)
    stability = max(0.1, state.stability_days)
    return min(1.0, max(0.0, math.pow(0.9, elapsed_days / stability)))


def infer_rating(
    *,
    correct: bool,
    independent: bool,
    hint_count: int,
    retry_count: int,
    response_time_ms: int | None,
    transfer: bool = False,
) -> FSRSRating:
    if not correct:
        return FSRSRating.AGAIN
    if not independent or hint_count > 0 or retry_count > 0:
        return FSRSRating.HARD
    if transfer or (response_time_ms is not None and response_time_ms <= 3000):
        return FSRSRating.EASY
    return FSRSRating.GOOD


def schedule_review(state: FSRSState, rating: FSRSRating, now: datetime) -> FSRSSchedule:
    current_r = retrievability(state, now) if state.review_count else 0.0
    difficulty_delta = {FSRSRating.AGAIN: 0.8, FSRSRating.HARD: 0.15, FSRSRating.GOOD: -0.15, FSRSRating.EASY: -0.35}[rating]
    difficulty = min(10.0, max(1.0, state.difficulty + difficulty_delta))
    if rating == FSRSRating.AGAIN:
        stability = max(0.25, state.stability_days * 0.45)
        interval = max(0.25, stability)
    else:
        growth = {
            FSRSRating.HARD: 1.35,
            FSRSRating.GOOD: 2.5,
            FSRSRating.EASY: 4.0,
        }[rating]
        overdue_bonus = 1.0 + max(0.0, 0.9 - current_r) * 0.5
        stability = max(0.5, state.stability_days * growth * overdue_bonus)
        interval = stability * {FSRSRating.HARD: 0.8, FSRSRating.GOOD: 1.0, FSRSRating.EASY: 1.25}[rating]
    return FSRSSchedule(
        rating=rating,
        difficulty=difficulty,
        stability_days=stability,
        retrievability=1.0,
        last_review_at=now,
        next_review_at=now + timedelta(days=interval),
        review_count=state.review_count + 1,
    )
