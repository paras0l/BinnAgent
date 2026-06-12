from datetime import datetime
from src.tools.srs import SRSCard, srs_scheduler, INTERVALS


class TestSRSCorrectAnswer:
    def test_srs_correct_answer(self):
        card = SRSCard(item_id="word_001", item_type="vocabulary")

        # First correct answer -> interval=1, confidence=0.2
        card = srs_scheduler.schedule_next(card, correct=True)
        assert card.interval_days == 1
        assert card.confidence == 0.2
        assert card.last_result is True
        assert card.review_count == 1
        assert card.next_review is not None

        # Second correct answer -> interval=2, confidence=0.4
        card = srs_scheduler.schedule_next(card, correct=True)
        assert card.interval_days == 2
        assert card.confidence == 0.4
        assert card.review_count == 2

        # Third correct answer -> interval=4, confidence=0.6
        card = srs_scheduler.schedule_next(card, correct=True)
        assert card.interval_days == 4
        assert card.confidence == 0.6
        assert card.review_count == 3


class TestSRSWrongAnswer:
    def test_srs_wrong_answer(self):
        card = SRSCard(item_id="word_002", item_type="vocabulary", confidence=0.6, review_count=3)

        card = srs_scheduler.schedule_next(card, correct=False)
        assert card.interval_days == 1
        assert card.confidence == 0.3
        assert card.last_result is False
        assert card.review_count == 2
        assert card.next_review is not None


class TestSRSRecommendDrill:
    def test_recommend_drill_filters_due_cards(self):
        now = datetime.now()
        card_due = SRSCard(item_id="due_1", item_type="vocabulary", next_review=now)
        card_future = SRSCard(
            item_id="future_1", item_type="vocabulary", next_review=now.replace(year=now.year + 1)
        )
        card_no_review = SRSCard(item_id="no_review", item_type="vocabulary")

        cards = [card_due, card_future, card_no_review]
        recommended = srs_scheduler.recommend_drill(cards, limit=10)
        assert card_due in recommended
        assert card_no_review in recommended
        assert card_future not in recommended
