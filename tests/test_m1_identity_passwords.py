from __future__ import annotations

import pytest

from backend.app.core.error_codes import ErrorCode
from backend.app.core.errors import AppError
from backend.app.domains.identity.passwords import Argon2PasswordHasher, PasswordPolicy, hash_password


class FakeHasher:
    def hash(self, password: str) -> str:
        return f"fake-hash:{len(password)}"

    def verify(self, password_hash: str, password: str) -> bool:
        return password_hash == self.hash(password)

    def needs_rehash(self, password_hash: str) -> bool:
        return False


def test_password_policy_accepts_three_character_categories() -> None:
    PasswordPolicy().validate("RepairKnowledge2026")
    assert hash_password("RepairKnowledge2026", hasher=FakeHasher()) == "fake-hash:19"


def test_real_argon2id_hash_is_salted_and_verifiable() -> None:
    hasher = Argon2PasswordHasher()
    first = hash_password("RepairKnowledge2026!", hasher=hasher)
    second = hash_password("RepairKnowledge2026!", hasher=hasher)

    assert first.startswith("$argon2id$")
    assert first != second
    assert hasher.verify(first, "RepairKnowledge2026!")
    assert not hasher.verify(first, "WrongPassword2026!")


@pytest.mark.parametrize("password", ["short", "alllowercaseonly", "A" * 129])
def test_password_policy_rejects_weak_or_oversized_values(password: str) -> None:
    with pytest.raises(AppError) as exc_info:
        PasswordPolicy().validate(password)
    assert exc_info.value.code == ErrorCode.PASSWORD_POLICY_VIOLATION
