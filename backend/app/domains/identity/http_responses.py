from __future__ import annotations

from fastapi import Request, Response
from fastapi.routing import APIRoute
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ...core.config import AppSettings
from ...core.contracts import ResponseMeta, V1Response
from ...core.request_context import request_id_from_request


def apply_no_store(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return response


class IdentityNoStoreRoute(APIRoute):
    """Apply identity cache policy to successes and handled error responses."""

    def get_route_handler(self):  # type: ignore[no-untyped-def]
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            response = await original(request)
            return apply_no_store(response)

        return handler


def identity_json_response(
    request: Request,
    data: object | None = None,
    *,
    status_code: int = 200,
    response_model: type[BaseModel] | None = None,
) -> JSONResponse:
    model = response_model or V1Response[object | None]
    payload = model(data=data, meta=ResponseMeta(requestId=request_id_from_request(request)))
    response = JSONResponse(status_code=status_code, content=jsonable_encoder(payload))
    return apply_no_store(response)  # type: ignore[return-value]


def set_session_cookie(
    response: JSONResponse,
    *,
    settings: AppSettings,
    token: str,
) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: JSONResponse, *, settings: AppSettings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )
