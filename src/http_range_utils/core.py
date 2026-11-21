"""Core parsing and formatting for HTTP byte ranges.

RFC 9110 defines two related header fields:

* ``Range: bytes=first-last, ...`` on a request, which may use suffix ranges
  (``-N``) and open-ended ranges (``N-``).
* ``Content-Range: bytes first-last/complete`` on a response, where the
  complete length may be ``*`` when it is unknown.

The parser normalizes both into absolute half-open byte intervals
``(start, end)`` where ``end`` is exclusive. This makes the two header fields
comparable and lets callers slice a ``bytes`` object directly.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

# A single range specifier, e.g. "0-99", "-50", "100-".
_RANGE_SPEC_RE = re.compile(r"^(\d*)-(\d*)$")


def _parse_non_negative_int(text: str, what: str) -> int:
    """Parse a decimal integer, rejecting signs and empty strings.

    ``int()`` accepts leading ``+``/``-`` and surrounding whitespace, which
    are not valid in the grammar. A regex keeps the accepted language exact.
    """
    if not text or not text.isdigit():
        raise ValueError(f"invalid {what}: {text!r}")
    return int(text)


def parse_range(
    value: str, complete_length: Optional[int] = None
) -> List[Tuple[int, int]]:
    """Parse a ``Range`` header field value into absolute half-open intervals.

    ``value`` is the full field value, including the ``bytes=`` unit, e.g.
    ``"bytes=0-99, 200-, -50"``.

    ``complete_length`` is the length of the representation being ranged
    over. It is required to resolve suffix ranges (``-N``) and to clamp
    open-ended ranges (``N-``) to the end of the representation. When it is
    ``None``, suffix ranges raise ``ValueError`` and open-ended ranges are
    returned with ``end`` equal to ``2**63 - 1``, an upper bound that callers
    can clamp themselves.

    Returns a list of ``(start, end)`` tuples with ``end`` exclusive. The
    list preserves the order of the field value. A syntactically valid but
    unsatisfiable range (``start >= complete_length``) is dropped, matching
    the behaviour a server needs: an empty list means the range cannot be
    satisfied.

    Raises ``ValueError`` for malformed input.
    """
    if not isinstance(value, str):
        raise ValueError("range value must be a string")

    parts = value.split("=", 1)
    if len(parts) != 2:
        raise ValueError(f"missing range unit in {value!r}")
    unit, specs_text = parts
    if unit.strip().lower() != "bytes":
        raise ValueError(f"unsupported range unit: {unit!r}")

    if complete_length is not None:
        if not isinstance(complete_length, int) or isinstance(complete_length, bool):
            raise ValueError("complete_length must be an int or None")
        if complete_length < 0:
            raise ValueError("complete_length must not be negative")

    specs = [s.strip() for s in specs_text.split(",")]
    if not specs or any(s == "" for s in specs):
        raise ValueError(f"empty range specifier in {value!r}")

    result: List[Tuple[int, int]] = []
    for spec in specs:
        match = _RANGE_SPEC_RE.match(spec)
        if match is None:
            raise ValueError(f"invalid range specifier: {spec!r}")
        first_text, last_text = match.groups()
        if first_text == "" and last_text == "":
            raise ValueError(f"range specifier has no bounds: {spec!r}")

        if first_text == "":
            # Suffix range: the last N bytes.
            if complete_length is None:
                raise ValueError(
                    "suffix ranges require complete_length to resolve"
                )
            suffix = _parse_non_negative_int(last_text, "suffix length")
            if suffix == 0:
                # A zero-length suffix can never be satisfied.
                continue
            start = max(0, complete_length - suffix)
            end = complete_length
        else:
            start = _parse_non_negative_int(first_text, "range start")
            if last_text == "":
                # Open-ended range: from start to the end of the representation.
                if complete_length is None:
                    end = 2**63 - 1
                else:
                    end = complete_length
            else:
                last = _parse_non_negative_int(last_text, "range end")
                if last < start:
                    raise ValueError(
                        f"range end {last} is before start {start} in {spec!r}"
                    )
                # The field is inclusive; the interval is half-open.
                end = last + 1

        if complete_length is not None and start >= complete_length:
            # Unsatisfiable; skip rather than error so a caller can detect an
            # empty result and reply 416.
            continue
        result.append((start, end))

    return result


def parse_content_range(value: str) -> Tuple[int, int, Optional[int]]:
    """Parse a ``Content-Range`` header field value.

    Returns ``(start, end, complete_length)`` where ``end`` is exclusive and
    ``complete_length`` is ``None`` for the ``*`` form. The value must use the
    ``bytes`` unit, e.g. ``"bytes 0-99/1234"`` or ``"bytes 0-99/*"``.

    Raises ``ValueError`` for malformed input.
    """
    if not isinstance(value, str):
        raise ValueError("content-range value must be a string")

    parts = value.split(" ", 1)
    if len(parts) != 2 or parts[0].strip().lower() != "bytes":
        raise ValueError(f"unsupported content-range unit in {value!r}")
    range_part, slash, complete_part = parts[1].strip().partition("/")
    if slash != "/":
        raise ValueError(f"missing complete-length in {value!r}")

    match = _RANGE_SPEC_RE.match(range_part)
    if match is None:
        raise ValueError(f"invalid content-range specifier: {range_part!r}")
    first_text, last_text = match.groups()
    if first_text == "" or last_text == "":
        # Content-Range intervals are always absolute and bounded.
        raise ValueError(f"content-range must have both bounds: {range_part!r}")

    start = _parse_non_negative_int(first_text, "content-range start")
    last = _parse_non_negative_int(last_text, "content-range end")
    if last < start:
        raise ValueError(
            f"content-range end {last} is before start {start} in {value!r}"
        )

    complete_part = complete_part.strip()
    if complete_part == "*":
        complete_length: Optional[int] = None
    else:
        complete_length = _parse_non_negative_int(
            complete_part, "complete length"
        )
        if last >= complete_length:
            raise ValueError(
                f"content-range end {last} is outside complete length "
                f"{complete_length} in {value!r}"
            )

    return start, last + 1, complete_length


def format_range(start: int, end: int) -> str:
    """Format a half-open interval as a ``Range`` header field value.

    ``end`` is exclusive, so ``format_range(0, 100)`` returns
    ``"bytes=0-99"``.
    """
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("start must be an int")
    if not isinstance(end, int) or isinstance(end, bool):
        raise ValueError("end must be an int")
    if start < 0 or end < 0:
        raise ValueError("start and end must not be negative")
    if end <= start:
        raise ValueError("end must be greater than start")
    return f"bytes={start}-{end - 1}"


def format_content_range(start: int, end: int, complete_length: Optional[int]) -> str:
    """Format a half-open interval as a ``Content-Range`` header field value.

    ``complete_length`` may be ``None`` to emit the ``*`` form.
    """
    if not isinstance(start, int) or isinstance(start, bool):
        raise ValueError("start must be an int")
    if not isinstance(end, int) or isinstance(end, bool):
        raise ValueError("end must be an int")
    if start < 0 or end < 0:
        raise ValueError("start and end must not be negative")
    if end <= start:
        raise ValueError("end must be greater than start")
    if complete_length is not None:
        if not isinstance(complete_length, int) or isinstance(complete_length, bool):
            raise ValueError("complete_length must be an int or None")
        if complete_length < 0:
            raise ValueError("complete_length must not be negative")
        if end > complete_length:
            raise ValueError("end exceeds complete_length")
    complete_text = "*" if complete_length is None else str(complete_length)
    return f"bytes {start}-{end - 1}/{complete_text}"
