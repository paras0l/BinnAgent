from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class SRSCard:
    item_id: str
    item_type: str
    review_count: int = 0
    confidence: float = 0.0  # 0.0 to 1.0
    last_result: Optional[bool] = None
    next_review: Optional[datetime] = None
    interval_days: int = 0


INTERVALS = [1, 2, 4, 7, 15, 30]


class SRSScheduler:
    """Simplified SM-2 SRS scheduler for spaced repetition learning."""

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def schedule_next(self, card: SRSCard, correct: bool) -> SRSCard:
        if correct:
            card.review_count += 1
            idx = min(card.review_count - 1, len(INTERVALS) - 1)
            card.interval_days = INTERVALS[idx]
            card.confidence = round(min(1.0, card.confidence + 0.2), 2)
        else:
            card.interval_days = 1
            card.review_count = max(0, card.review_count - 1)
            card.confidence = round(max(0.0, card.confidence - 0.3), 2)

        card.last_result = correct
        card.next_review = datetime.now(timezone.utc) + timedelta(days=card.interval_days)
        return card

    def recommend_drill(self, cards: list[SRSCard], limit: int = 10) -> list[SRSCard]:
        now = datetime.now(timezone.utc)
        due_now = [
            c for c in cards if c.next_review is None or self._as_utc(c.next_review) <= now
        ]
        sorted_cards = sorted(due_now, key=lambda c: c.confidence)
        return sorted_cards[:limit]


srs_scheduler = SRSScheduler()
