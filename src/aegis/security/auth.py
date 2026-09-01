"""Authentication: HMAC-SHA256 signed tokens and the provider.

Tokens are `aegis.v1.<payload-b64>.<signature>` where the signature is an
HMAC-SHA256 of the payload under the provider's secret key. Verification uses a
constant-time compare. Production should switch the secret to a KMS/Vault-backed
SecretsProvider; the token format does not change.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Any

from aegis.domain import InsufficientPermission, Role, ValidationFailed
from aegis.domain.time import UTC

from .models import AuthContext, AuthMethod, Credentials
from .ports import AuthProvider

_VERSION = "aegis.v1"
_ALGORITHM = "sha256"


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class HmacTokenAuthProvider(AuthProvider):
    """Issues and verifies signed identity tokens using a shared secret."""

    def __init__(self, secret: str, token_ttl: timedelta = timedelta(hours=8)) -> None:
        if not secret:
            raise ValidationFailed("auth provider requires a non-empty secret")
        self._secret = secret.encode("utf-8")
        self._ttl = token_ttl

    def issue(
        self,
        user_id: str,
        organization_id: str,
        role: Role,
        project_id: str | None = None,
        method: AuthMethod = AuthMethod.OAUTH2,
        now: datetime | None = None,
    ) -> str:
        """Issue a signed token for a known actor (used by the login path)."""
        issued = now or datetime.now(UTC)
        payload = {
            "sub": user_id,
            "org": organization_id,
            "prj": project_id,
            "role": role.value,
            "auth": method.value,
            "iat": issued.timestamp(),
            "exp": (issued + self._ttl).timestamp(),
        }
        body = _b64_encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
        return f"{_VERSION}.{body}.{self._sign(body)}"

    def authenticate(self, credentials: Credentials) -> AuthContext:
        token = credentials.bearer_token or credentials.api_key or credentials.service_account_token
        if token is None:
            raise InsufficientPermission("no credentials supplied")
        return self.validate_token(token)

    def validate_token(self, token: str, now: datetime | None = None) -> AuthContext:
        parts = token.rsplit(".", 2)
        if len(parts) != 3 or parts[0] != _VERSION:
            raise InsufficientPermission("malformed token")
        body, signature = parts[1], parts[2]
        if not hmac.compare_digest(signature, self._sign(body)):
            raise InsufficientPermission("token signature mismatch")
        try:
            payload: dict[str, Any] = json.loads(_b64_decode(body))
        except (ValueError, TypeError) as exc:
            raise InsufficientPermission("token payload is not decodable") from exc
        verified = now or datetime.now(UTC)
        expiry = datetime.fromtimestamp(float(payload["exp"]), tz=UTC)
        if expiry <= verified:
            raise InsufficientPermission("token expired")
        return AuthContext(
            user_id=str(payload["sub"]),
            organization_id=str(payload["org"]),
            project_id=payload.get("prj"),
            role=Role(str(payload["role"])),
            authentication_method=AuthMethod(str(payload["auth"])),
            authenticated_at=datetime.fromtimestamp(float(payload["iat"]), tz=UTC),
            token_expiry=expiry,
        )

    def _sign(self, body: str) -> str:
        digest = hmac.new(self._secret, body.encode("utf-8"), hashlib.sha256).digest()
        return _b64_encode(digest)


__all__ = ["AuthContext", "HmacTokenAuthProvider"]
