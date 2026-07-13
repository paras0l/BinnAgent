"""Runtime policy for AI-generated iframe widgets.

The policy deliberately never enables same-origin, storage, top navigation, or
unrestricted domains. Those boundaries are not safe to delegate to generated code.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_DOMAIN = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_PROFILES = {"strict", "interactive", "trusted_integration"}


@dataclass(frozen=True)
class SandboxPermissionState:
    profile: str = "strict"
    allowed_domains: tuple[str, ...] = ()

    @property
    def allow_network(self) -> bool:
        return self.profile == "trusted_integration" and bool(self.allowed_domains)

    def payload(self) -> dict[str, object]:
        return {
            "profile": self.profile,
            "allow_network": self.allow_network,
            "allowed_domains": list(self.allowed_domains),
            "allow_same_origin": False,
            "allow_storage": False,
            "allow_navigation": False,
            "allow_popups": False,
        }


_active = SandboxPermissionState()


def normalize_domains(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    normalized = {value.strip().lower() for value in values if isinstance(value, str) and value.strip()}
    invalid = [value for value in normalized if not _DOMAIN.fullmatch(value)]
    if invalid:
        raise ValueError("allowed domains must be hostnames without scheme or path")
    return tuple(sorted(normalized))[:20]


def configure_sandbox_permissions(profile: str, allowed_domains: list[str] | tuple[str, ...]) -> SandboxPermissionState:
    if profile not in _PROFILES:
        raise ValueError("unsupported sandbox profile")
    global _active
    domains = normalize_domains(allowed_domains)
    _active = SandboxPermissionState(profile=profile, allowed_domains=domains)
    return _active


def sandbox_permissions() -> SandboxPermissionState:
    return _active


def sandbox_csp(state: SandboxPermissionState | None = None) -> str:
    active = state or sandbox_permissions()
    connect_src = " ".join(f"https://{domain}" for domain in active.allowed_domains) if active.allow_network else "'none'"
    return (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; "
        f"connect-src {connect_src}; media-src 'none'; font-src 'none'; frame-src 'none'; child-src 'none'; "
        "object-src 'none'; form-action 'none'; base-uri 'none'; navigate-to 'none'"
    )
