from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class PasswordChangeRequest(BaseModel):
    currentPassword: str = Field(min_length=1, max_length=1024)
    newPassword: str = Field(min_length=1, max_length=128)


class UserIdentityView(BaseModel):
    id: str
    displayName: str
    roles: list[str]
    permissions: list[str]
    mustChangePassword: bool


class SessionView(BaseModel):
    expiresAt: str
    idleExpiresAt: str


class LoginView(BaseModel):
    user: UserIdentityView
    session: SessionView
    csrfToken: str


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    displayName: str = Field(min_length=1, max_length=128)
    initialPassword: str = Field(min_length=1, max_length=128)
    roles: list[str] = Field(default_factory=list)


class UserProfileUpdateRequest(BaseModel):
    displayName: str = Field(min_length=1, max_length=128)


class UserStatusRequest(BaseModel):
    isActive: bool
    reason: str = Field(min_length=1, max_length=256)


class UserRolesRequest(BaseModel):
    roles: list[str] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=256)


class UserPasswordResetRequest(BaseModel):
    temporaryPassword: str = Field(min_length=1, max_length=128)
    reason: str = Field(min_length=1, max_length=256)
