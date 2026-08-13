"""M0-owned discovery point for domain ORM metadata used by Alembic."""

from __future__ import annotations

from importlib import import_module


# A domain adds models only beneath its own package. M0 imports these optional
# modules before Alembic reads Base.metadata, avoiding edits to app.db.models
# or alembic/env.py by every domain team.
DOMAIN_MODEL_MODULES = (
    "domains.identity.models",
    "domains.audit.models",
    "domains.documents.models",
    "domains.knowledge.models",
    "domains.devices.models",
    "domains.workflows.models",
    "domains.rag.models",
    "workers.models",
    "indexing.models",
)


def _is_missing_module(exc: ModuleNotFoundError, module_name: str) -> bool:
    missing_name = exc.name or ""
    return module_name == missing_name or module_name.startswith(f"{missing_name}.")


def load_domain_models() -> None:
    """Import delivered domain models while surfacing their real import errors."""

    app_package = __package__.rsplit(".db", maxsplit=1)[0]
    for module_suffix in DOMAIN_MODEL_MODULES:
        module_name = f"{app_package}.{module_suffix}"
        try:
            import_module(module_name)
        except ModuleNotFoundError as exc:
            if _is_missing_module(exc, module_name):
                continue
            raise
