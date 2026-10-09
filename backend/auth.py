"""OIDC bearer authentication and role checks."""

from __future__ import annotations

from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request
from jwt import PyJWKClient

from config import auth_disabled, oidc_audience, oidc_issuer

ROLE_ORDER = ("viewer", "editor", "approver")
_jwk_clients: dict[str, PyJWKClient] = {}


@dataclass
class Principal:
    subject: str
    email: str
    name: str
    roles: set[str]

    def has(self, role: str) -> bool:
        if "admin" in self.roles:
            return True
        if role not in ROLE_ORDER:
            return role in self.roles
        needed = ROLE_ORDER.index(role)
        return any(ROLE_ORDER.index(owned) >= needed for owned in self.roles if owned in ROLE_ORDER)


def local_admin() -> Principal:
    return Principal(
        subject="local-admin",
        email="admin@localhost",
        name="Local Admin",
        roles={"admin", "approver", "editor", "viewer"},
    )


def _roles_from_claims(claims: dict) -> set[str]:
    roles: set[str] = set()
    raw = claims.get("roles") or claims.get("groups") or []
    if isinstance(raw, str):
        raw = [raw]
    roles.update(str(role) for role in raw)
    realm = (claims.get("realm_access") or {}).get("roles") or []
    roles.update(str(role) for role in realm)
    resource = claims.get("resource_access") or {}
    for access in resource.values():
        roles.update(str(role) for role in (access.get("roles") or []))
    recognized = {role for role in roles if role in {"admin", *ROLE_ORDER}}
    return recognized or {"viewer"}


def verify_oidc_token(token: str) -> dict:
    issuer = oidc_issuer()
    audience = oidc_audience()
    if not issuer or not audience:
        raise HTTPException(status_code=503, detail="OIDC issuer and audience are not configured")
    client = _jwk_clients.get(issuer)
    if client is None:
        client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
        _jwk_clients[issuer] = client
    try:
        key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256", "RS384", "RS512"],
            audience=audience,
            issuer=issuer,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid bearer token") from exc


def get_current_user(request: Request) -> Principal:
    if auth_disabled():
        principal = local_admin()
        request.state.principal = principal
        return principal

    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    claims = verify_oidc_token(authorization.split(" ", 1)[1].strip())
    principal = Principal(
        subject=str(claims.get("sub") or ""),
        email=str(claims.get("email") or claims.get("preferred_username") or ""),
        name=str(claims.get("name") or claims.get("preferred_username") or claims.get("sub") or ""),
        roles=_roles_from_claims(claims),
    )
    request.state.principal = principal
    return principal


def require_role(role: str):
    def checker(principal: Principal = Depends(get_current_user)) -> Principal:
        if not principal.has(role):
            raise HTTPException(status_code=403, detail=f"{role} role required")
        return principal

    return checker
