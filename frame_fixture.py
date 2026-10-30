"""Test-only complete-buffer decoder; this does not define a production wire format.

The fixture uses a four-byte big-endian length and JSON solely to exercise
general bounded-framing and duplicate-field failure cases. No IPC or identity
is established. Successful decoding is never an authorization or DURABLE ack.
"""

import json
import math
import re


MAX_FIXTURE_PAYLOAD = 4096
ID = re.compile(r"[A-Za-z0-9_-]{1,64}\Z", re.ASCII)
FIELDS = frozenset({"version", "kind", "run", "role", "sequence", "request", "payload"})


class Rejected(ValueError):
    """A malformed fixture; this attempt cannot be accepted."""


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Rejected("duplicate key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise Rejected("non-finite JSON constant")


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise Rejected("floating-point overflow")
    return result


def _reject_surrogates(value):
    if isinstance(value, str):
        if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
            raise Rejected("unpaired surrogate")
    elif isinstance(value, dict):
        for key, nested in value.items():
            _reject_surrogates(key)
            _reject_surrogates(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_surrogates(nested)


def decode_fixture(frame):
    """Decode exactly one complete fixture or reject it. No partial buffer state."""
    if not isinstance(frame, bytes) or len(frame) < 4:
        raise Rejected("missing length")
    size = int.from_bytes(frame[:4], "big")
    if size == 0 or size > MAX_FIXTURE_PAYLOAD or len(frame) != 4 + size:
        raise Rejected("invalid, truncated or trailing frame")
    try:
        body = frame[4:].decode("utf-8", errors="strict")
        value = json.loads(body, object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant, parse_float=_finite_float)
        _reject_surrogates(value)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise Rejected("invalid fixture JSON") from error
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise Rejected("missing or unknown field")
    if type(value["version"]) is not int or value["version"] != 1:
        raise Rejected("fixture version")
    if value["kind"] not in ("event", "producer_done"):
        raise Rejected("fixture kind")
    for field in ("run", "role", "request"):
        if not isinstance(value[field], str) or ID.fullmatch(value[field]) is None:
            raise Rejected("invalid fixture identifier")
    if type(value["sequence"]) is not int or not 1 <= value["sequence"] <= 4096:
        raise Rejected("fixture sequence")
    if not isinstance(value["payload"], dict):
        raise Rejected("fixture payload shape")
    return value
