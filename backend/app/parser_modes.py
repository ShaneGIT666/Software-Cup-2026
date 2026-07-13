from __future__ import annotations

from dataclasses import dataclass
import os

from fastapi import HTTPException


PARSER_MODES = ("text_fast", "smart_multimodal", "full_visual")
DEFAULT_PARSER_MODE = "smart_multimodal"
PARSER_MODE_ERROR = "parser_mode must be one of text_fast, smart_multimodal, full_visual"


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _mineru_timeout(name: str, default: int) -> int:
    legacy = _env_int("MINERU_TIMEOUT_SECONDS", default, 30)
    return _env_int(name, legacy, 30)


@dataclass(frozen=True)
class ParserPolicy:
    mode: str
    use_mineru: bool
    mineru_timeout_seconds: int
    render_scope: str
    render_dpi: int
    visual_page_limit: int
    analyze_mineru_assets: bool
    require_renderer: bool


def resolve_parser_policy(mode: str | None) -> ParserPolicy:
    normalized = (mode or DEFAULT_PARSER_MODE).strip().lower()
    if normalized not in PARSER_MODES:
        raise HTTPException(status_code=422, detail=PARSER_MODE_ERROR)
    if normalized == "text_fast":
        return ParserPolicy(
            mode=normalized,
            use_mineru=False,
            mineru_timeout_seconds=0,
            render_scope="none",
            render_dpi=0,
            visual_page_limit=0,
            analyze_mineru_assets=False,
            require_renderer=False,
        )
    if normalized == "full_visual":
        return ParserPolicy(
            mode=normalized,
            use_mineru=True,
            mineru_timeout_seconds=_mineru_timeout("MINERU_FULL_TIMEOUT_SECONDS", 600),
            render_scope="all",
            render_dpi=_env_int("FULL_VISUAL_DPI", 180, 72),
            visual_page_limit=_env_int("FULL_VISUAL_MAX_PAGES", 300),
            analyze_mineru_assets=True,
            require_renderer=True,
        )
    return ParserPolicy(
        mode=normalized,
        use_mineru=True,
        mineru_timeout_seconds=_mineru_timeout("MINERU_SMART_TIMEOUT_SECONDS", 180),
        render_scope="candidates",
        render_dpi=_env_int("SMART_VISUAL_DPI", 120, 72),
        visual_page_limit=_env_int("SMART_VISUAL_MAX_PAGES", 80),
        analyze_mineru_assets=False,
        require_renderer=True,
    )
