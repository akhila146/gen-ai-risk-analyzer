
import logging
import os
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientConnectionError, PyJWKClientError

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


class OktaVerifier:
    """Verify signatures and authorization claims against a configured Okta server."""

    def __init__(self) -> None:
        """Fail closed when required deployment configuration is missing or invalid."""
        self.issuer = os.environ.get("OKTA_ISSUER", "").strip().rstrip("/")
        self.audience = os.environ.get("OKTA_AUDIENCE", "").strip()
        self.client_id = os.environ.get("OKTA_CLIENT_ID", "").strip()
        self.scope = os.environ.get("OKTA_REQUIRED_SCOPE", "").strip()
        parsed = urlsplit(self.issuer)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or not parsed.path.startswith("/oauth2/")
            or not parsed.path.removeprefix("/oauth2/")
            or not self.audience
            or not self.client_id
            or not self.scope
            or any(character.isspace() for character in self.scope)
        ):
            raise RuntimeError(
                "Configure OKTA_ISSUER (HTTPS custom authorization server), "
                "OKTA_AUDIENCE, OKTA_CLIENT_ID, and OKTA_REQUIRED_SCOPE."
            )
        self.jwks = PyJWKClient(
            f"{self.issuer}/v1/keys", cache_jwk_set=True, lifespan=300, timeout=5
        )

    def verify(self, token: str) -> dict[str, Any]:
        """Accept only signed, unexpired API tokens for this issuer, client, and scope."""
        unauthorized = HTTPException(
            status_code=401,
            detail="A valid Okta access token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
                raise InvalidTokenError("Unsupported token header")
            key = self.jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "cid"]},
            )
        except PyJWKClientConnectionError:
            logger.warning("Okta signing keys are temporarily unavailable")
            raise HTTPException(
                status_code=503, detail="Sign-in verification is temporarily unavailable."
            ) from None
        except (InvalidTokenError, PyJWKClientError):
            raise unauthorized from None

        if not claims["sub"] or claims["cid"] != self.client_id:
            raise unauthorized
        scopes = claims.get("scp")
        if not isinstance(scopes, list) or self.scope not in scopes:
            raise HTTPException(status_code=403, detail="Workspace access is not permitted.")
        return claims


@lru_cache(maxsize=1)
def get_okta_verifier() -> OktaVerifier:
    """Reuse the bounded signing-key cache across requests."""
    return OktaVerifier()


def require_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, Any]:
    """Run blocking key discovery in FastAPI's worker pool, never its event loop."""
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Sign in with Okta to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_okta_verifier().verify(credentials.credentials)
