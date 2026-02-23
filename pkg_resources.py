from __future__ import annotations

from importlib import import_module
from importlib import resources as _resources
from pathlib import Path


def resource_filename(package: str, resource: str) -> str:
    """
    Minimal shim for pkg_resources.resource_filename used by open-rppg.
    Resolves a resource path inside an installed package.
    """
    module = import_module(package)
    try:
        return str(_resources.files(module).joinpath(resource))
    except Exception:
        base = Path(module.__file__).resolve().parent
        return str(base / resource)
