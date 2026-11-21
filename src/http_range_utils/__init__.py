"""Parse and normalize HTTP Range and Content-Range header field syntax.

Exports:
    parse_range(value, complete_length=None) -> list[tuple[int, int]]
    parse_content_range(value) -> tuple[int, int, int | None]
    format_range(start, end) -> str
    format_content_range(start, end, complete_length) -> str
"""

from .core import (
    parse_range,
    parse_content_range,
    format_range,
    format_content_range,
)

__all__ = [
    "parse_range",
    "parse_content_range",
    "format_range",
    "format_content_range",
]
