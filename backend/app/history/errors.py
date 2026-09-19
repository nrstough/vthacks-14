"""The one error this package raises. Its own module so every submodule can
raise it without importing the package root, which would be circular."""

from __future__ import annotations


class ImportRefused(ValueError):
    """The rows cannot be planned. Always the caller's input, never a bug."""
