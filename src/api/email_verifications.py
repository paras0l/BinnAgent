from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db_session
from src.auth.email_verification import (
    EmailDeliveryError,
    create_email_verification_token,
    deliver_verification_code,
    generate_code_salt,
    generate_verification_code,
    hash_verification_code,
    normalize_email,
    utc_now,
    verification_code_matches,
)
from src.config import settings
from src.models.auth import EmailVerificationChallenge


router = APIRouter(prefix="/api/email-verifications", tags=["email-verifications"])


class RequestEmailVerification(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)


class ConfirmEmailVerification(RequestEmailVerification):
    code: str = Field(pattern=r"^\d{6}$")


class EmailVerificationRequestedResponse(BaseModel):
    email: str
    expires_in_seconds: int
    resend_after_seconds: int


class EmailVerificationConfirmedResponse(BaseModel):
    email: str
    verification_token: str
    expires_in_seconds: int


@router.post("", response_model=EmailVerificationRequestedResponse, status_code=status.HTTP_202_ACCEPTED)
async def request_email_verification(
    body: RequestEmailVerification,
    db: AsyncSession = Depends(get_db_session),
) -> EmailVerificationRequestedResponse:
    now = utc_now()
    latest_result = await db.execute(
        select(EmailVerificationChallenge)
        .where(EmailVerificationChallenge.email == body.email)
        .order_by(EmailVerificationChallenge.sent_at.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    if latest is not None:
        elapsed = (now - latest.sent_at).total_seconds()
        if elapsed < settings.email_verification_resend_seconds:
            retry_after = max(1, settings.email_verification_resend_seconds - int(elapsed))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {retry_after} seconds before requesting another code",
                headers={"Retry-After": str(retry_after)},
            )

    code = generate_verification_code()
    salt = generate_code_salt()
    challenge = EmailVerificationChallenge(
        email=body.email,
        code_hash=hash_verification_code(email=body.email, code=code, salt=salt),
        code_salt=salt,
        sent_at=now,
        expires_at=now + timedelta(seconds=settings.email_verification_code_ttl_seconds),
    )
    db.add(challenge)
    await db.flush()
    try:
        await deliver_verification_code(email=body.email, code=code)
    except EmailDeliveryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Verification email could not be sent",
        ) from exc

    return EmailVerificationRequestedResponse(
        email=body.email,
        expires_in_seconds=settings.email_verification_code_ttl_seconds,
        resend_after_seconds=settings.email_verification_resend_seconds,
    )


@router.post("/confirm", response_model=EmailVerificationConfirmedResponse)
async def confirm_email_verification(
    body: ConfirmEmailVerification,
    db: AsyncSession = Depends(get_db_session),
) -> EmailVerificationConfirmedResponse:
    now = utc_now()
    result = await db.execute(
        select(EmailVerificationChallenge)
        .where(
            EmailVerificationChallenge.email == body.email,
            EmailVerificationChallenge.verified_at.is_(None),
        )
        .order_by(EmailVerificationChallenge.sent_at.desc())
        .limit(1)
        .with_for_update()
    )
    challenge = result.scalar_one_or_none()
    if challenge is None or challenge.expires_at < now:
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")
    if challenge.attempt_count >= settings.email_verification_max_attempts:
        raise HTTPException(status_code=429, detail="Too many verification attempts")

    challenge.attempt_count += 1
    if not verification_code_matches(
        email=body.email,
        code=body.code,
        salt=challenge.code_salt,
        expected_hash=challenge.code_hash,
    ):
        await db.commit()
        raise HTTPException(status_code=400, detail="Verification code is invalid or expired")

    challenge.verified_at = now
    await db.flush()
    return EmailVerificationConfirmedResponse(
        email=body.email,
        verification_token=create_email_verification_token(email=body.email, now=now),
        expires_in_seconds=settings.email_verification_token_ttl_seconds,
    )
