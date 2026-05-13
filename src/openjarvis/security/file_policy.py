"""File sensitivity policy — block access to secrets, credentials, and keys."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Union

DEFAULT_SENSITIVE_PATTERNS: frozenset[str] = frozenset(
    {
        ".env",
        ".env.*",
        "*.env",
        ".secret",
        "*.secrets",
        "credentials.*",
        "*.pem",
        "*.key",
        "*.p12",
        "*.pfx",
        "*.jks",
        "id_rsa",
        "id_ed25519",
        ".htpasswd",
        ".pgpass",
        ".netrc",
    }
)

PROTECTED_WRITE_ROOTS: tuple[str, ...] = (
    "/bin",
    "/etc",
    "/private/etc",
    "/sbin",
    "/System",
    "/usr",
)

PROTECTED_PATH_PARTS: frozenset[str] = frozenset(
    {
        ".aws",
        ".docker",
        ".gnupg",
        ".kube",
        ".ssh",
    }
)


def has_path_traversal(path: Union[str, Path]) -> bool:
    """Return ``True`` when a path uses explicit parent traversal."""
    return ".." in Path(path).parts


def is_sensitive_file(path: Union[str, Path]) -> bool:
    """Return ``True`` if *path* matches a sensitive file pattern.

    Checks both the filename and the full name against
    ``DEFAULT_SENSITIVE_PATTERNS`` using :func:`fnmatch.fnmatch`.
    Uses the Rust implementation when available, falls back to Python.
    """
    try:
        from openjarvis._rust_bridge import get_rust_module

        _rust = get_rust_module()
        return _rust.is_sensitive_file(str(path))
    except ImportError:
        return _is_sensitive_file_py(str(path))


def is_protected_path(path: Union[str, Path]) -> bool:
    """Return ``True`` for paths tools should never write or patch."""
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return True

    if any(part in PROTECTED_PATH_PARTS for part in resolved.parts):
        return True

    for root in PROTECTED_WRITE_ROOTS:
        root_path = Path(root).expanduser().resolve()
        try:
            if resolved == root_path or resolved.is_relative_to(root_path):
                return True
        except ValueError:
            continue
    return False


def is_path_within_roots(
    path: Union[str, Path],
    allowed_roots: Sequence[Union[str, Path]],
) -> bool:
    """Return ``True`` when *path* resolves under one configured root."""
    if not allowed_roots:
        return True
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return False
    for root in allowed_roots:
        try:
            root_path = Path(root).expanduser().resolve()
            if resolved == root_path or resolved.is_relative_to(root_path):
                return True
        except (OSError, ValueError):
            continue
    return False


def is_sensitive_path(path: Union[str, Path]) -> bool:
    """Return ``True`` when the input or resolved target is sensitive."""
    if is_sensitive_file(path):
        return True
    try:
        resolved = Path(path).expanduser().resolve()
    except (OSError, ValueError):
        return True
    return is_sensitive_file(resolved)


def _is_sensitive_file_py(path_str: str) -> bool:
    """Pure-Python fallback for sensitive file detection."""
    import fnmatch

    p = Path(path_str)
    name = p.name
    for pattern in DEFAULT_SENSITIVE_PATTERNS:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(str(p), pattern):
            return True
    return False


def filter_sensitive_paths(paths: Iterable[Union[str, Path]]) -> List[Path]:
    """Return only non-sensitive paths from *paths*."""
    return [Path(p) for p in paths if not is_sensitive_file(p)]


__all__ = [
    "DEFAULT_SENSITIVE_PATTERNS",
    "PROTECTED_PATH_PARTS",
    "PROTECTED_WRITE_ROOTS",
    "filter_sensitive_paths",
    "has_path_traversal",
    "is_sensitive_file",
    "is_sensitive_path",
    "is_path_within_roots",
    "is_protected_path",
]
