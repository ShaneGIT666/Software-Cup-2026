from __future__ import annotations

from importlib import import_module

from fastapi import APIRouter


# M0 owns this registry so a domain team never has to edit the v1 root router.
# A module is optional until its owning module is delivered. Any import error
# inside an existing module is still raised rather than hidden.
DOMAIN_ROUTER_MODULES = (
    "auth",
    "users",
    "audit",
    "documents",
    "knowledge",
    "devices",
    "workflows",
    "search",
    "rag",
    "operations",
)


def _is_missing_module(exc: ModuleNotFoundError, module_name: str) -> bool:
    missing_name = exc.name or ""
    return module_name == missing_name or module_name.startswith(f"{missing_name}.")


def include_domain_routers(root_router: APIRouter) -> None:
    for module_suffix in DOMAIN_ROUTER_MODULES:
        module_name = f"{__package__}.{module_suffix}"
        try:
            module = import_module(module_name)
        except ModuleNotFoundError as exc:
            if _is_missing_module(exc, module_name):
                continue
            raise

        router = getattr(module, "router", None)
        if not isinstance(router, APIRouter):
            raise TypeError(f"{module_name}.router 必须是 FastAPI APIRouter")
        root_router.include_router(router)
