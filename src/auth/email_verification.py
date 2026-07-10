import asyncio
import base64
from datetime import datetime, timezone
from email.message import EmailMessage
import hashlib
import hmac
import json
import logging
import re
import secrets
import smtplib
import ssl

from src.config import settings


logger = logging.getLogger(__name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class EmailDeliveryError(RuntimeError):
    pass


def normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("A valid email address is required")
    return normalized


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def generate_code_salt() -> str:
    return secrets.token_hex(16)


def hash_verification_code(*, email: str, code: str, salt: str) -> str:
    payload = f"{email}:{code}:{salt}".encode()
    return hmac.new(settings.email_verification_secret.encode(), payload, hashlib.sha256).hexdigest()


def verification_code_matches(*, email: str, code: str, salt: str, expected_hash: str) -> bool:
    actual_hash = hash_verification_code(email=email, code=code, salt=salt)
    return hmac.compare_digest(actual_hash, expected_hash)


def create_email_verification_token(*, email: str, now: datetime | None = None) -> str:
    issued_at = now or utc_now()
    payload = {
        "email": email,
        "exp": int(issued_at.timestamp()) + settings.email_verification_token_ttl_seconds,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    )
    signature = hmac.new(
        settings.email_verification_secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def email_verification_token_is_valid(
    *,
    email: str,
    token: str,
    now: datetime | None = None,
) -> bool:
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        expected_signature = hmac.new(
            settings.email_verification_secret.encode(),
            encoded_payload.encode(),
            hashlib.sha256,
        ).digest()
        provided_signature = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_signature, provided_signature):
            return False
        payload = json.loads(_base64url_decode(encoded_payload))
        current_timestamp = int((now or utc_now()).timestamp())
        return payload.get("email") == email and int(payload.get("exp", 0)) >= current_timestamp
    except (TypeError, ValueError, json.JSONDecodeError):
        return False


async def deliver_verification_code(*, email: str, code: str) -> None:
    mode = settings.email_delivery_mode.strip().lower()
    if mode == "console":
        logger.warning("BinnAgent email verification code for %s: %s", email, code)
        return
    if mode != "smtp":
        raise EmailDeliveryError("Unsupported email delivery mode")
    if not settings.smtp_host or not settings.smtp_from_address:
        raise EmailDeliveryError("SMTP is not configured")

    try:
        await asyncio.to_thread(_deliver_via_smtp, email, code)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Unable to send verification email") from exc


def _deliver_via_smtp(email: str, code: str) -> None:
    message = EmailMessage()
    message["Subject"] = "BinnAgent 邮箱验证码"
    message["From"] = settings.smtp_from_address
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "你正在验证 BinnAgent 学习账号邮箱。",
                "",
                f"验证码：{code}",
                f"验证码将在 {settings.email_verification_code_ttl_seconds // 60} 分钟后失效。",
                "如果不是你本人操作，请忽略此邮件。",
            ]
        )
    )

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    smtp_kwargs = {"host": settings.smtp_host, "port": settings.smtp_port, "timeout": 10}
    if settings.smtp_use_ssl:
        smtp_kwargs["context"] = ssl.create_default_context()
    with smtp_class(**smtp_kwargs) as smtp:
        if settings.smtp_starttls and not settings.smtp_use_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
