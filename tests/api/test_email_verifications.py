from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import deps
from src.auth.email_verification import (
    create_email_verification_token,
    email_verification_token_is_valid,
    hash_verification_code,
    utc_now,
)
from src.main import app
from src.models.auth import EmailVerificationChallenge


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    app.dependency_overrides[deps.get_db_session] = lambda: session
    yield session
    app.dependency_overrides.clear()


class TestRequestEmailVerification:
    @pytest.mark.asyncio
    async def test_sends_code_and_stores_only_hash(self, client, mock_session, monkeypatch):
        latest_result = MagicMock()
        latest_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=latest_result)
        deliver = AsyncMock()
        monkeypatch.setattr(
            "src.api.email_verifications.generate_verification_code",
            lambda: "123456",
        )
        monkeypatch.setattr("src.api.email_verifications.deliver_verification_code", deliver)

        response = await client.post(
            "/api/email-verifications",
            json={"email": " Alice@example.com "},
        )

        assert response.status_code == 202
        assert response.json()["email"] == "alice@example.com"
        challenge = mock_session.add.call_args.args[0]
        assert isinstance(challenge, EmailVerificationChallenge)
        assert challenge.code_hash != "123456"
        assert len(challenge.code_hash) == 64
        deliver.assert_awaited_once_with(email="alice@example.com", code="123456")

    @pytest.mark.asyncio
    async def test_enforces_resend_cooldown(self, client, mock_session):
        now = utc_now()
        latest = EmailVerificationChallenge(
            email="alice@example.com",
            code_hash="hash",
            code_salt="salt",
            attempt_count=0,
            sent_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = latest
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/email-verifications",
            json={"email": "alice@example.com"},
        )

        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1
        mock_session.add.assert_not_called()


class TestConfirmEmailVerification:
    @pytest.mark.asyncio
    async def test_valid_code_returns_email_bound_token(self, client, mock_session):
        now = utc_now()
        salt = "0123456789abcdef0123456789abcdef"
        challenge = EmailVerificationChallenge(
            email="alice@example.com",
            code_hash=hash_verification_code(
                email="alice@example.com",
                code="123456",
                salt=salt,
            ),
            code_salt=salt,
            attempt_count=0,
            sent_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = challenge
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/email-verifications/confirm",
            json={"email": "alice@example.com", "code": "123456"},
        )

        assert response.status_code == 200
        token = response.json()["verification_token"]
        assert email_verification_token_is_valid(email="alice@example.com", token=token)
        assert not email_verification_token_is_valid(email="other@example.com", token=token)
        assert challenge.verified_at is not None
        assert challenge.attempt_count == 1

    @pytest.mark.asyncio
    async def test_wrong_code_increments_persisted_attempt_count(self, client, mock_session):
        now = utc_now()
        challenge = EmailVerificationChallenge(
            email="alice@example.com",
            code_hash="0" * 64,
            code_salt="salt",
            attempt_count=0,
            sent_at=now,
            expires_at=now + timedelta(minutes=10),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = challenge
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/email-verifications/confirm",
            json={"email": "alice@example.com", "code": "123456"},
        )

        assert response.status_code == 400
        assert challenge.attempt_count == 1
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_expired_code_is_rejected(self, client, mock_session):
        now = utc_now()
        challenge = EmailVerificationChallenge(
            email="alice@example.com",
            code_hash="0" * 64,
            code_salt="salt",
            attempt_count=0,
            sent_at=now - timedelta(minutes=11),
            expires_at=now - timedelta(minutes=1),
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = challenge
        mock_session.execute = AsyncMock(return_value=result)

        response = await client.post(
            "/api/email-verifications/confirm",
            json={"email": "alice@example.com", "code": "123456"},
        )

        assert response.status_code == 400


def test_verification_token_rejects_tampering_and_expiry() -> None:
    now = utc_now()
    token = create_email_verification_token(email="alice@example.com", now=now)

    assert not email_verification_token_is_valid(
        email="alice@example.com",
        token=f"{token}x",
        now=now,
    )
    assert not email_verification_token_is_valid(
        email="alice@example.com",
        token=token,
        now=now + timedelta(hours=1),
    )
