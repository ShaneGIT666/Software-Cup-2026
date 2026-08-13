from __future__ import annotations

import unicodedata


_ALLOWED_PUNCTUATION = frozenset("._-@")


def normalize_username(value: str) -> str:
    """Normalize a human account name for lookup and uniqueness.

    The original spelling remains in ``users.username`` for display/audit;
    only this canonical value is used for login and unique constraints.
    """

    if len(value) > 256:
        raise ValueError("用户名必须为 3 到 128 个字符")
    normalized = unicodedata.normalize("NFKC", value).strip().casefold()
    if not 3 <= len(normalized) <= 128:
        raise ValueError("用户名必须为 3 到 128 个字符")
    if normalized[0] in _ALLOWED_PUNCTUATION or normalized[-1] in _ALLOWED_PUNCTUATION:
        raise ValueError("用户名不能以标点开头或结尾")
    if not all(character.isalnum() or character in _ALLOWED_PUNCTUATION for character in normalized):
        raise ValueError("用户名只能包含 Unicode 字母、数字及 . _ - @")
    return normalized
