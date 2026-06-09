from __future__ import annotations

import secrets
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid() -> str:
    timestamp_ms = int(time.time() * 1000)
    random_bits = secrets.randbits(80)
    return _encode_crockford(timestamp_ms, 10) + _encode_crockford(random_bits, 16)


def new_request_id() -> str:
    return f"req_{new_ulid().lower()}"


def new_job_id() -> str:
    return f"job_{new_ulid().lower()}"


def new_artifact_id() -> str:
    return f"art_{new_ulid().lower()}"


def new_audit_id() -> str:
    return f"aud_{new_ulid().lower()}"
