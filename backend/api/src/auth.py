from __future__ import annotations

import os
from functools import lru_cache
from typing import Any
from urllib.parse import urlparse

import jwt
from fastapi import Header, HTTPException, status


WorkspaceRole = str
ROLE_OWNER = "owner"
ROLE_MANAGER = "manager"
ROLE_PURCHASING_LEAD = "purchasing_lead"
ROLE_ANALYST = "analyst"
VALID_WORKSPACE_ROLES = {
    ROLE_OWNER,
    ROLE_MANAGER,
    ROLE_PURCHASING_LEAD,
    ROLE_ANALYST,
}


def _token_from_header(authorization: str | None) -> str | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return authorization.split(" ", 1)[1]


@lru_cache(maxsize=1)
def _jwks_client() -> jwt.PyJWKClient | None:
    jwks_url = _normalized_jwks_url()
    issuer = os.getenv("CLERK_ISSUER")

    # Ignore template/example values and derive the JWKS URL from the active issuer instead.
    if jwks_url and "your-instance" in jwks_url:
        jwks_url = None

    if not jwks_url and issuer:
        jwks_url = issuer.rstrip("/") + "/.well-known/jwks.json"

    if not jwks_url:
        return None
    return jwt.PyJWKClient(jwks_url)


def _normalized_jwks_url() -> str | None:
    raw_value = os.getenv("CLERK_JWKS_URL", "").strip()
    if not raw_value:
        return None
    if raw_value.startswith("CLERK_JWKS_URL="):
        raw_value = raw_value.split("=", 1)[1].strip()
    parsed = urlparse(raw_value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return raw_value


def _use_local_dev_token_fallback() -> bool:
    if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return False
    if os.getenv("ALLOW_DEV_AUTH_FALLBACK", "").strip().lower() not in {"1", "true", "yes"}:
        return False
    issuer = os.getenv("CLERK_ISSUER", "")
    secret_key = os.getenv("CLERK_SECRET_KEY", "")
    return secret_key.startswith("sk_test_") or ".clerk.accounts.dev" in issuer


def _allowed_token_algorithms(token: str) -> list[str]:
    allowed = {"RS256", "ES256"}
    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        return ["RS256"]

    algorithm = header.get("alg")
    if isinstance(algorithm, str) and algorithm in allowed:
        return [algorithm]
    return ["RS256"]


def _verify_session_payload(token: str) -> dict[str, Any]:
    jwks_client = _jwks_client()
    issuer = os.getenv("CLERK_ISSUER")

    if not jwks_client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured for protected routes",
        )

    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=_allowed_token_algorithms(token),
        issuer=issuer if issuer else None,
        options={"verify_aud": False},
        leeway=60,
    )


def _decode_session_payload(authorization: str | None) -> dict[str, Any]:
    token = _token_from_header(authorization)

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    if _use_local_dev_token_fallback():
        try:
            payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                    "verify_iss": False,
                    "verify_aud": False,
                },
                algorithms=["RS256", "HS256"],
            )
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Invalid development session token") from exc
        subject = payload.get("sub")
        if not subject:
            raise HTTPException(status_code=401, detail="Missing user identity in session token")
        return payload

    try:
        payload = _verify_session_payload(token)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid session token") from exc

    subject = payload.get("sub")
    if not subject:
        raise HTTPException(status_code=401, detail="Missing user identity in session token")
    return payload


def resolve_actor_id(authorization: str | None) -> str:
    return str(_decode_session_payload(authorization).get("sub"))


def _role_from_metadata(payload: dict[str, Any]) -> WorkspaceRole | None:
    metadata_candidates = [
        payload.get("workspace_role"),
        payload.get("role"),
        payload.get("org_role"),
    ]
    for metadata_key in ("public_metadata", "private_metadata", "metadata"):
        metadata = payload.get(metadata_key)
        if isinstance(metadata, dict):
            metadata_candidates.extend(
                [
                    metadata.get("workspace_role"),
                    metadata.get("role"),
                    metadata.get("supplychain_role"),
                ]
            )

    for candidate in metadata_candidates:
        if not isinstance(candidate, str):
            continue
        normalized = candidate.strip().lower().replace("-", "_")
        if normalized in VALID_WORKSPACE_ROLES:
            return normalized
    return None


def resolve_workspace_role(
    authorization: str | None,
    development_role: str | None = None,
) -> WorkspaceRole:
    payload = _decode_session_payload(authorization)
    metadata_role = _role_from_metadata(payload)
    if metadata_role:
        return metadata_role

    if _use_local_dev_token_fallback():
        header_role = (development_role or "").strip().lower().replace("-", "_")
        if header_role in VALID_WORKSPACE_ROLES:
            return header_role
        return ROLE_OWNER

    fallback_role = os.getenv("WORKSPACE_DEFAULT_ROLE", ROLE_ANALYST).strip().lower().replace("-", "_")
    if fallback_role in VALID_WORKSPACE_ROLES:
        return fallback_role
    return ROLE_ANALYST


def actor_id_from_request(authorization: str | None = Header(default=None)) -> str:
    return resolve_actor_id(authorization)


def require_workspace_role(*allowed_roles: WorkspaceRole):
    allowed = set(allowed_roles)

    def dependency(
        authorization: str | None = Header(default=None),
        development_role: str | None = Header(default=None, alias="X-Workspace-Role"),
    ) -> WorkspaceRole:
        role = resolve_workspace_role(authorization, development_role=development_role)
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these workspace roles: {', '.join(sorted(allowed))}",
            )
        return role

    return dependency


def auth_debug_info(authorization: str | None) -> dict[str, Any]:
    token = _token_from_header(authorization)
    issuer = os.getenv("CLERK_ISSUER")
    jwks_url = _normalized_jwks_url()
    if not token:
        return {
            "has_authorization_header": bool(authorization),
            "has_bearer_token": False,
            "configured_issuer": issuer,
            "configured_jwks_url": jwks_url,
            "error": "Missing bearer token",
        }

    unverified_payload: dict[str, Any] = {}
    unverified_header: dict[str, Any] = {}
    try:
        unverified_header = jwt.get_unverified_header(token)
        unverified_payload = jwt.decode(
            token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_iss": False,
                "verify_aud": False,
            },
            algorithms=["RS256", "ES256", "HS256"],
        )
    except Exception as exc:
        return {
            "has_authorization_header": True,
            "has_bearer_token": True,
            "configured_issuer": issuer,
            "configured_jwks_url": jwks_url,
            "error": f"Could not decode token payload: {exc}",
        }

    try:
        payload = _verify_session_payload(token)
        actor_id = payload.get("sub")
        verified = True
        verification_error = None
        verification_error_type = None
    except Exception as exc:
        actor_id = None
        verified = False
        verification_error = str(exc)
        verification_error_type = type(exc).__name__

    return {
        "has_authorization_header": True,
        "has_bearer_token": True,
        "configured_issuer": issuer,
        "configured_jwks_url": jwks_url,
        "token_algorithm": unverified_header.get("alg"),
        "token_key_id_present": bool(unverified_header.get("kid")),
        "token_type": unverified_header.get("typ"),
        "token_issuer": unverified_payload.get("iss"),
        "token_subject_present": bool(unverified_payload.get("sub")),
        "token_audience": unverified_payload.get("aud"),
        "token_authorized_party": unverified_payload.get("azp"),
        "verified": verified,
        "actor_id_present": bool(actor_id),
        "verification_error": verification_error,
        "verification_error_type": verification_error_type,
    }
