# http-range-utils

Parse and normalize the HTTP `Range` and `Content-Range` header field syntax
into absolute half-open byte intervals.

```python
from http_range_utils import parse_range, parse_content_range

# A request may ask for several pieces, use a suffix, or leave the end open.
parse_range("bytes=0-99, 200-, -50", complete_length=1000)
# [(0, 100), (200, 1000), (950, 1000)]

# A response states the interval it carries and the full length, or '*'.
parse_content_range("bytes 0-99/1234")
# (0, 100, 1234)
parse_content_range("bytes 0-99/*")
# (0, 100, None)
```

Both parsers return `(start, end)` pairs where `end` is exclusive, so the
result can be used directly to slice a `bytes` object. `format_range` and
`format_content_range` are the inverse operations.

## Why this exists

The two header fields look alike but behave differently: `Range` may contain
suffix (`-50`) and open-ended (`200-`) specifiers, and its values are relative
to a representation whose length the request does not carry. `Content-Range`
is always absolute and bounded, but its complete length may be unknown (`*`).
A server that wants to answer a range request has to reconcile the two, and
doing that with ad-hoc string splitting is where off-by-one and unsatisfiable
range bugs live. This library makes the normalization explicit: every value
becomes a half-open interval, and an interval that cannot be satisfied is
dropped rather than silently mis-sliced.

The trade-off is that `parse_range` needs `complete_length` to resolve suffix
and open-ended ranges. Without it, suffix ranges raise `ValueError` and an
open-ended range is returned with `end = 2**63 - 1`; callers that know the
length should pass it. This keeps the parser honest about what it cannot know
instead of guessing.

## The awkward edge

A syntactically valid range can still be unsatisfiable. `parse_range` returns
an empty list for `"bytes=1000-1099"` over a 1000-byte representation, so a
caller can distinguish "the client asked for nothing usable" from "the field
was malformed". Malformed input raises `ValueError`.

## API

- `parse_range(value, complete_length=None) -> list[tuple[int, int]]`
- `parse_content_range(value) -> tuple[int, int, int | None]`
- `format_range(start, end) -> str`
- `format_content_range(start, end, complete_length) -> str`
