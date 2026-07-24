"""Load every ORM model for standalone administrative commands."""

from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules

from collegefootballfantasy_api.app import models


def load_all_models() -> None:
    """Register all current model mappers before opening a script-owned session."""
    for module in iter_modules(models.__path__):
        if module.name != "registry":
            import_module(f"{models.__name__}.{module.name}")
