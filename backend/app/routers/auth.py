"""
Logging in with your phone number:
  1. POST /v1/auth/send-code  {phone}        -> we text a 6-digit code
  2. POST /v1/auth/verify     {phone, code}  -> tokens (you're logged in)
"""

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app import otp
from app.config import get_settings
from app.deps import Db
from app.models import User
from app.schemas import PhoneIn, RefreshIn, TokensOut, UserOut, VerifyIn
from app.security import (
    create_access_token,
    create_refresh_token,
    revoke_refresh_token,
    use_refresh_token,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def issue_tokens(db: Db, user: User) -> TokensOut:
    refresh = create_refresh_token(db, user.id)
    db.commit()
    return TokensOut(
        access_token=create_access_token(user.id),
        refresh_token=refresh,
        expires_in=get_settings().access_token_minutes * 60,
        user=UserOut(id=user.id, phone=user.phone, display_name=user.display_name),
    )


@router.post("/send-code", status_code=status.HTTP_204_NO_CONTENT)
def send_code(body: PhoneIn) -> Response:
    try:
        otp.send_code(body.phone)
    except otp.OtpError as error:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/verify")
def verify(body: VerifyIn, db: Db) -> TokensOut:
    try:
        ok = otp.check_code(body.phone, body.code)
    except otp.OtpError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That code isn't right. Try again.")

    # First login with this number creates the account.
    user = db.scalar(select(User).where(User.phone == body.phone))
    if user is None:
        user = User(phone=body.phone)
        db.add(user)
        db.flush()
    return issue_tokens(db, user)


@router.post("/refresh")
def refresh(body: RefreshIn, db: Db) -> TokensOut:
    user_id = use_refresh_token(db, body.refresh_token)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Please log in again")
    return issue_tokens(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshIn, db: Db) -> Response:
    revoke_refresh_token(db, body.refresh_token)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
