from __future__ import annotations

import importlib.abc
import sys


class _DisableMakoPygmentsForAlembic(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path: object | None = None, target: object | None = None):
        if fullname == "mako.ext.pygmentplugin":
            raise ImportError("Mako Pygments highlighting is disabled for Alembic startup")
        return None


if any("alembic" in arg for arg in sys.argv):
    sys.meta_path.insert(0, _DisableMakoPygmentsForAlembic())
