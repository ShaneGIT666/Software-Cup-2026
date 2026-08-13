"""Cross-cutting application primitives shared by every domain module."""
from .concurrency import etag_for_version, parse_if_match, require_matching_version
from .pagination import decode_cursor, encode_cursor
from .trusted_origins import require_trusted_browser_origin

__all__ = [
    "decode_cursor",
    "encode_cursor",
    "etag_for_version",
    "parse_if_match",
    "require_matching_version",
    "require_trusted_browser_origin",
]
