import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Cookie, HTTPException, Request, Response, status
from pydantic import BaseModel, StringConstraints, field_validator, model_validator

from database import sessions_collection, users_collection

AUTH_COOKIE_NAME = "riskscope_session"
SESSION_LIFETIME = timedelta(days=7)
PASSWORD_MIN_LENGTH = 12
EMAIL_PATTERN = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,63}$")
AUTH_COOKIE_SECURE = os.getenv(
    "AUTH_COOKIE_SECURE",
    "true" if os.getenv("FRONTEND_URL", "").startswith("https://") else "false",
).lower() in {"1", "true", "yes"}
FULL_NAME = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
EMAIL = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
PASSWORD = Annotated[str, StringConstraints(min_length=PASSWORD_MIN_LENGTH, max_length=1024)]


class SignupRequest(BaseModel):
    full_name: FULL_NAME
    email: EMAIL
    password: PASSWORD
    confirm_password: PASSWORD

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize and validate the account email address."""
        normalized = value.lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        """Require the password confirmation to match."""
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class LoginRequest(BaseModel):
    email: EMAIL
    password: Annotated[str, StringConstraints(min_length=1, max_length=1024)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalize and validate the login email address."""
        normalized = value.lower()
        if not EMAIL_PATTERN.fullmatch(normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


def hash_password(password: str) -> str:
    """Hash a password with a unique salt using scrypt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "scrypt${}${}${}${}${}".format(
        2**14,
        8,
        1,
        salt.hex(),
        digest.hex(),
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password against a stored scrypt hash."""
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded_hash.split("$")
        if algorithm != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError, TypeError):
        return False


def token_digest(token: str) -> str:
    """Return the one-way digest used to store opaque tokens."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def public_user(user: dict) -> dict:
    """Return account fields that are safe to send to the frontend."""
    return {
        "id": str(user["_id"]),
        "full_name": user["full_name"],
        "email": user["email"],
    }


async def create_session(user_id, response: Response) -> None:
    """Create a database-backed session and set its protected browser cookie."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + SESSION_LIFETIME
    await sessions_collection.insert_one(
        {"token_hash": token_digest(token), "user_id": user_id, "expires_at": expires_at}
    )
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
    )


async def get_current_user(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=AUTH_COOKIE_NAME)] = None,
) -> dict:
    """Resolve a valid cookie session or reject protected requests."""
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    session = await sessions_collection.find_one(
        {
            "token_hash": token_digest(session_token),
            "expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    user = await users_collection.find_one({"_id": session["user_id"]})
    if not user:
        await sessions_collection.delete_one({"_id": session["_id"]})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return user


async def register_account(request: SignupRequest) -> dict:
    """Create a unique account without starting an authenticated session."""
    from pymongo.errors import DuplicateKeyError

    user = {
        "full_name": request.full_name,
        "email": request.email,
        "password_hash": hash_password(request.password),
        "created_at": datetime.now(timezone.utc),
    }
    try:
        result = await users_collection.insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="An account with this email already exists.") from None
    user["_id"] = result.inserted_id
    return public_user(user)


async def login_account(request: LoginRequest, response: Response) -> dict:
    """Verify credentials and start a persistent authenticated session."""
    user = await users_collection.find_one({"email": request.email})
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    await create_session(user["_id"], response)
    return public_user(user)


async def logout_account(request: Request, response: Response) -> dict:
    """Revoke the current server-side session and clear its browser cookie."""
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        await sessions_collection.delete_one({"token_hash": token_digest(token)})
    response.delete_cookie(
        AUTH_COOKIE_NAME,
        httponly=True,
        secure=AUTH_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    return {"message": "Logged out successfully."}
