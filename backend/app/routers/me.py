"""Your account: name, and permanently deleting everything."""

from fastapi import APIRouter, Response, status

from app.cache import clear_history_cache
from app.deps import CurrentUser, Db
from app.schemas import ProfileIn, UserOut

router = APIRouter(prefix="/v1/me", tags=["me"])


@router.get("")
def get_me(user: CurrentUser) -> UserOut:
    return UserOut(id=user.id, phone=user.phone, display_name=user.display_name)


@router.put("")
def update_me(body: ProfileIn, user: CurrentUser, db: Db) -> UserOut:
    user.display_name = body.display_name
    db.commit()
    return UserOut(id=user.id, phone=user.phone, display_name=user.display_name)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: Db) -> Response:
    """
    Deletes the account and, through "on delete cascade", every row about it:
    Circle, check-ins (including an active one), SOS history and logins.
    Google Play requires apps with accounts to offer this.
    """
    user_id = str(user.id)
    db.delete(user)
    db.commit()
    clear_history_cache(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
