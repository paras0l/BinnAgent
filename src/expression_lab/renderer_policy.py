from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Final


SANDBOX_CSP: Final[str] = (
    "default-src 'none'; "
    "script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; "
    "img-src data:; "
    "connect-src 'none'; media-src 'none'; font-src 'none'; "
    "frame-src 'none'; child-src 'none'; object-src 'none'; "
    "form-action 'none'; base-uri 'none'; navigate-to 'none'"
)


@dataclass(frozen=True)
class RendererPolicy:
    allowed_tags: frozenset[str]
    allowed_attributes: frozenset[str]
    allowed_svg_attributes: frozenset[str]
    allowed_events: frozenset[str]
    sandbox_attribute: str = "allow-scripts"
    max_html_bytes: int = 40_000
    max_css_bytes: int = 30_000
    max_javascript_bytes: int = 30_000
    max_timeout_ms: int = 10_000
    csp: str = SANDBOX_CSP


@dataclass(frozen=True)
class SanitizedSandbox:
    html: str
    css: str
    javascript: str
    issues: tuple[str, ...]
    sandbox_attribute: str = "allow-scripts"
    csp: str = SANDBOX_CSP


_POLICY = RendererPolicy(
    allowed_tags=frozenset(
        {
            "div",
            "span",
            "p",
            "strong",
            "em",
            "small",
            "section",
            "article",
            "main",
            "header",
            "footer",
            "h1",
            "h2",
            "h3",
            "h4",
            "ul",
            "ol",
            "li",
            "button",
            "label",
            "input",
            "textarea",
            "select",
            "option",
            "progress",
            "meter",
            "br",
            "hr",
            "svg",
            "g",
            "path",
            "circle",
            "ellipse",
            "rect",
            "line",
            "polyline",
            "polygon",
            "text",
            "tspan",
            "defs",
            "lineargradient",
            "radialgradient",
            "stop",
            "clippath",
        }
    ),
    allowed_attributes=frozenset(
        {
            "id",
            "class",
            "title",
            "role",
            "aria-label",
            "aria-describedby",
            "aria-live",
            "aria-pressed",
            "aria-selected",
            "tabindex",
            "type",
            "name",
            "value",
            "placeholder",
            "checked",
            "selected",
            "disabled",
            "readonly",
            "min",
            "max",
            "step",
            "rows",
            "cols",
            "data-id",
            "data-value",
            "data-action-id",
        }
    ),
    allowed_svg_attributes=frozenset(
        {
            "viewbox",
            "width",
            "height",
            "x",
            "y",
            "x1",
            "y1",
            "x2",
            "y2",
            "cx",
            "cy",
            "r",
            "rx",
            "ry",
            "d",
            "points",
            "fill",
            "fill-opacity",
            "stroke",
            "stroke-width",
            "stroke-linecap",
            "stroke-linejoin",
            "stroke-dasharray",
            "opacity",
            "transform",
            "text-anchor",
            "font-size",
            "offset",
            "stop-color",
            "stop-opacity",
            "clip-path",
        }
    ),
    allowed_events=frozenset(
        {
            "selection_changed",
            "answer_submitted",
            "interaction",
            "action",
            "answer",
            "change",
        }
    ),
)


def renderer_policy() -> RendererPolicy:
    """Return the immutable policy shared by validation and iframe rendering."""

    return _POLICY


class _AllowlistHtmlParser(HTMLParser):
    _void_tags = frozenset({"br", "hr", "input"})
    _drop_content_tags = frozenset(
        {"script", "style", "iframe", "object", "embed", "form", "link", "meta", "base"}
    )

    def __init__(self, policy: RendererPolicy) -> None:
        super().__init__(convert_charrefs=True)
        self.policy = policy
        self.parts: list[str] = []
        self.issues: list[str] = []
        self._drop_depth = 0
        self._open_tags: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        if tag in self._drop_content_tags:
            self._drop_depth += 1
            self.issues.append(f"removed_tag:{tag}")
            return
        if self._drop_depth:
            return
        if tag not in self.policy.allowed_tags:
            self.issues.append(f"removed_tag:{tag}")
            return
        clean_attrs: list[str] = []
        allowed = self.policy.allowed_attributes | self.policy.allowed_svg_attributes
        for raw_name, raw_value in attrs:
            name = raw_name.casefold()
            value = raw_value or ""
            if name.startswith("on") or name in {"style", "src", "srcset", "href", "action"}:
                self.issues.append(f"removed_attribute:{name}")
                continue
            if name not in allowed:
                self.issues.append(f"removed_attribute:{name}")
                continue
            clean_attrs.append(f' {name}="{html.escape(value, quote=True)}"')
        self.parts.append(f"<{tag}{''.join(clean_attrs)}>")
        if tag not in self._void_tags:
            self._open_tags.append(tag)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        lowered = tag.casefold()
        if lowered not in self._void_tags and self._open_tags and self._open_tags[-1] == lowered:
            self._open_tags.pop()
            self.parts.append(f"</{lowered}>")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self._drop_content_tags and self._drop_depth:
            self._drop_depth -= 1
            return
        if self._drop_depth or tag not in self.policy.allowed_tags or tag in self._void_tags:
            return
        if tag in self._open_tags:
            while self._open_tags:
                opened = self._open_tags.pop()
                self.parts.append(f"</{opened}>")
                if opened == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self._drop_depth:
            self.parts.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        if not self._drop_depth:
            self.parts.append(f"&{name};")

    def close(self) -> None:
        super().close()
        while self._open_tags:
            self.parts.append(f"</{self._open_tags.pop()}>")


def sanitize_html(value: str, *, policy: RendererPolicy | None = None) -> tuple[str, tuple[str, ...]]:
    active_policy = policy or renderer_policy()
    bounded = value.encode("utf-8")[: active_policy.max_html_bytes].decode(
        "utf-8", errors="ignore"
    )
    parser = _AllowlistHtmlParser(active_policy)
    try:
        parser.feed(bounded)
        parser.close()
    except Exception:
        return "", ("invalid_html",)
    return "".join(parser.parts), tuple(dict.fromkeys(parser.issues))


_DANGEROUS_CSS = re.compile(
    r"@(?:import|namespace|font-face|document|supports)|"
    r"url\s*\(|expression\s*\(|behavior\s*:|-moz-binding|javascript\s*:|"
    r"position\s*:\s*fixed",
    re.IGNORECASE,
)
_CSS_AT_STATEMENT = re.compile(
    r"@(?:import|namespace|charset)[^;{}]*(?:;|$)|"
    r"@(?:font-face|document|supports|media|keyframes)[^{}]*\{(?:[^{}]|\{[^{}]*\})*\}",
    re.IGNORECASE,
)
_CSS_RULE = re.compile(r"([^{}]+)\{([^{}]*)\}")
_SAFE_CSS_PROPERTY = re.compile(r"^[a-zA-Z-]{1,60}\s*:\s*[^;{}]{0,500}$")


def sanitize_css(value: str, *, scope: str | None = None) -> tuple[str, tuple[str, ...]]:
    active_policy = renderer_policy()
    bounded = value.encode("utf-8")[: active_policy.max_css_bytes].decode(
        "utf-8", errors="ignore"
    )
    issues: list[str] = []
    if _CSS_AT_STATEMENT.search(bounded):
        issues.append("removed_css_at_rule")
    bounded = _CSS_AT_STATEMENT.sub("", bounded)
    if _DANGEROUS_CSS.search(bounded):
        issues.append("removed_dangerous_css")
    bounded = _DANGEROUS_CSS.sub("", bounded)
    clean_rules: list[str] = []
    for selector_text, body in _CSS_RULE.findall(bounded):
        selectors: list[str] = []
        for raw_selector in selector_text.split(","):
            selector = raw_selector.strip()
            if not selector or selector.startswith("@") or any(
                token in selector.casefold() for token in ("html", "body", ":root")
            ):
                issues.append("removed_css_selector")
                continue
            selectors.append(f"{scope} {selector}" if scope else selector)
        declarations = []
        for declaration in body.split(";"):
            declaration = declaration.strip()
            if declaration and _SAFE_CSS_PROPERTY.fullmatch(declaration):
                declarations.append(declaration)
            elif declaration:
                issues.append("removed_css_declaration")
        if selectors and declarations:
            clean_rules.append(f"{', '.join(selectors)} {{{'; '.join(declarations)}}}")
    return "\n".join(clean_rules), tuple(dict.fromkeys(issues))


_DANGEROUS_JAVASCRIPT = re.compile(
    r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|Worker|SharedWorker|"
    r"importScripts|sendBeacon|eval|Function|indexedDB|localStorage|sessionStorage|"
    r"cookieStore|caches)\b|"
    r"document\s*\.\s*cookie|window\s*\.\s*(?:parent|top|opener)|"
    r"\b(?:parent|top|opener)\s*\.|\bpostMessage\s*\(|"
    r"\blocation\s*(?:=|\.)|\bopen\s*\(",
    re.IGNORECASE,
)


def sanitize_javascript(value: str) -> tuple[str, tuple[str, ...]]:
    active_policy = renderer_policy()
    bounded = value.encode("utf-8")[: active_policy.max_javascript_bytes].decode(
        "utf-8", errors="ignore"
    )
    if not bounded.strip():
        return "", ()
    if _DANGEROUS_JAVASCRIPT.search(bounded):
        return "", ("removed_dangerous_javascript",)
    # The iframe host injects the frozen `binnagent.emit(type, payload)` bridge.
    # Keeping bridge construction in one place prevents protocol drift and makes
    # every message pass the host's source/nonce/schema checks.
    return '"use strict";\n' + bounded, ()


def sanitize_sandbox_widget(
    html_value: str,
    css_value: str,
    javascript_value: str,
) -> SanitizedSandbox:
    clean_html, html_issues = sanitize_html(html_value)
    clean_css, css_issues = sanitize_css(css_value)
    clean_javascript, javascript_issues = sanitize_javascript(javascript_value)
    return SanitizedSandbox(
        html=clean_html,
        css=clean_css,
        javascript=clean_javascript,
        issues=tuple(dict.fromkeys((*html_issues, *css_issues, *javascript_issues))),
    )
