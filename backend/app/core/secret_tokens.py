"""Random tokens of the form `<scheme>_<prefix>_<secret>`, used by API keys
and invitations.

The prefix finds the stored record and is safe to show; the secret is 32
random bytes, of which only a SHA-256 hash is stored. A fast hash is enough
here, unlike for passwords: the secret is random and long, so guessing it
from its hash is not feasible.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field


@dataclass(frozen=True)
class IssuedToken:
    prefix: str
    secret_hash: str
    # The full token, to hand over once; kept out of reprs and logs.
    value: str = field(repr=False)


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def issue_token(scheme: str) -> IssuedToken:
    prefix = secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    return IssuedToken(prefix, hash_secret(secret), f"{scheme}_{prefix}_{secret}")


def split_token(scheme: str, presented: str) -> tuple[str, str] | None:
    """The prefix and secret of `presented`, if it has the shape of a token
    of `scheme`."""
    given_scheme, _, rest = presented.partition("_")
    prefix, _, secret = rest.partition("_")
    if given_scheme != scheme or not prefix or not secret:
        return None
    return prefix, secret


def secret_matches(secret: str, stored_hash: str | None) -> bool:
    """Whether `secret` hashes to `stored_hash`, compared in constant time so
    the response time does not reveal how much of it matched. A missing
    record (`None`) costs the same work and never matches."""
    expected = stored_hash if stored_hash is not None else hash_secret("")
    return hmac.compare_digest(hash_secret(secret), expected) and (
        stored_hash is not None
    )
