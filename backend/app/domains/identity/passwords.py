from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from ...core.error_codes import ErrorCode
from ...core.errors import AppError


class PasswordHasherPort(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password_hash: str, password: str) -> bool: ...

    def needs_rehash(self, password_hash: str) -> bool: ...


@dataclass(frozen=True)
class PasswordPolicy:
    min_length: int = 12
    max_length: int = 128

    def validate(self, password: str) -> None:
        if not self.min_length <= len(password) <= self.max_length:
            self._reject()
        categories = (
            re.search(r"[a-z]", password),
            re.search(r"[A-Z]", password),
            re.search(r"\d", password),
            re.search(r"[^A-Za-z0-9]", password),
        )
        if sum(bool(category) for category in categories) < 3:
            self._reject()

    @staticmethod
    def _reject() -> None:
        raise AppError(
            400,
            ErrorCode.PASSWORD_POLICY_VIOLATION,
            "密码必须为 12 到 128 位，并至少包含三类字符。",
        )


class Argon2PasswordHasher:
    """Argon2id adapter; import is deferred so configuration checks still run."""

    def __init__(self) -> None:
        try:
            from argon2 import PasswordHasher
            from argon2.low_level import Type
        except ImportError as exc:  # pragma: no cover - deployment dependency failure
            raise RuntimeError("M1 本地账户模式需要安装 argon2-cffi") from exc
        self._hasher = PasswordHasher(type=Type.ID)

    def hash(self, password: str) -> str:
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        from argon2.exceptions import InvalidHashError, VerifyMismatchError

        try:
            return bool(self._hasher.verify(password_hash, password))
        except (InvalidHashError, VerifyMismatchError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        return bool(self._hasher.check_needs_rehash(password_hash))


def hash_password(password: str, *, hasher: PasswordHasherPort | None = None) -> str:
    PasswordPolicy().validate(password)
    return (hasher or Argon2PasswordHasher()).hash(password)

