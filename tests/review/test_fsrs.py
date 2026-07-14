from datetime import datetime, timedelta, timezone

from src.adaptive.fsrs import FSRSRating, FSRSState, retrievability, schedule_review

T0 = datetime(2026, 7, 14, 10, tzinfo=timezone.utc)


def test_fsrs_rating_intervals_are_ordered() -> None:
    state = FSRSState()
    again = schedule_review(state, FSRSRating.AGAIN, T0)
    hard = schedule_review(state, FSRSRating.HARD, T0)
    good = schedule_review(state, FSRSRating.GOOD, T0)
    easy = schedule_review(state, FSRSRating.EASY, T0)
    assert again.next_review_at < hard.next_review_at < good.next_review_at < easy.next_review_at


def test_retrievability_declines_with_time() -> None:
    state = FSRSState(stability_days=7, last_review_at=T0, review_count=1)
    assert retrievability(state, T0 + timedelta(days=7)) < retrievability(
        state, T0 + timedelta(days=1)
    )


def test_successful_review_increases_stability() -> None:
    state = FSRSState(stability_days=3, last_review_at=T0, review_count=2)
    reviewed = schedule_review(state, FSRSRating.GOOD, T0 + timedelta(days=4))
    assert reviewed.stability_days > state.stability_days
