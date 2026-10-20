"""The seal on each audit record: an HMAC-SHA256 over the record's fields and
the seal of the record before it in the same chain.

Changing a sealed record, or dropping one from the middle, breaks every seal
from there on, and only the holder of AUDIT_CHAIN_KEY can seal them again.
The key is not in the database, so the owner of the tables, who can change
any row, cannot. services/audit_chain_service.py keeps the chains; the
migration that sealed the existing history calls `seal` as well, so the
function stays free of the ORM.

The fields are written as canonical JSON (sorted keys, no spaces, UTF-8), so
the same record always gives the same bytes. The record's id is not among
them: the database assigns it on insert, and the API's role may not update a
row afterwards to add a seal that covers it. The event type is the label the
database stores (`'LOGIN_SUCCESS'`), so the migration can read it as is.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime

# The "seal" before the first record of a chain.
GENESIS = "0" * 64


def seal(
    key: bytes,
    *,
    previous: str,
    chain_seq: int,
    event_type: str,
    user_id: int | None,
    target_user_id: int | None,
    organization_id: int | None,
    email: str | None,
    ip_address: str | None,
    message: str | None,
    created_at: datetime,
) -> str:
    """The hex HMAC-SHA256 of one record, chained to `previous`."""
    fields = {
        "chain_seq": chain_seq,
        "created_at": created_at.astimezone(UTC).isoformat(timespec="microseconds"),
        "email": email,
        "event_type": event_type,
        "ip_address": ip_address,
        "message": message,
        "organization_id": organization_id,
        "previous": previous,
        "target_user_id": target_user_id,
        "user_id": user_id,
    }
    payload = json.dumps(
        fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hmac.new(key, payload, hashlib.sha256).hexdigest()
