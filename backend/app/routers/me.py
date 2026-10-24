"""Your account: name, profile picture, and permanently deleting everything."""

from fastapi import APIRouter, HTTPException, Response, UploadFile, status

from app.cache import clear_history_cache
from app.deps import CurrentUser, Db
from app.models import ProfilePhoto, User, utcnow
from app.photos import read_photo
from app.schemas import ProfileIn, UserOut

router = APIRouter(prefix="/v1/me", tags=["me"])


def user_out(db: Db, user: User) -> UserOut:
    photo = db.get(ProfilePhoto, user.id)
    return UserOut(
        id=user.id,
        phone=user.phone,
        display_name=user.display_name,
        photo_updated_at=photo.updated_at if photo else None,
    )


@router.get("")
def get_me(user: CurrentUser, db: Db) -> UserOut:
    return user_out(db, user)


@router.put("")
def update_me(body: ProfileIn, user: CurrentUser, db: Db) -> UserOut:
    user.display_name = body.display_name
    db.commit()
    return user_out(db, user)


@router.put("/photo")
async def upload_profile_photo(photo: UploadFile, user: CurrentUser, db: Db) -> UserOut:
    """Your profile picture (JPEG or PNG, at most 5 MB), shown to your Circle in alerts."""
    content, content_type = await read_photo(photo)
    existing = db.get(ProfilePhoto, user.id)
    if existing is None:
        db.add(ProfilePhoto(user_id=user.id, content_type=content_type, content=content))
    else:
        existing.content_type, existing.content = content_type, content
        existing.updated_at = utcnow()
    db.commit()
    return user_out(db, user)


@router.get("/photo")
def get_profile_photo(user: CurrentUser, db: Db) -> Response:
    photo = db.get(ProfilePhoto, user.id)
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile picture")
    return Response(
        photo.content, media_type=photo.content_type, headers={"Cache-Control": "no-store"}
    )


@router.delete("/photo")
def delete_profile_photo(user: CurrentUser, db: Db) -> UserOut:
    photo = db.get(ProfilePhoto, user.id)
    if photo is not None:
        db.delete(photo)
        db.commit()
    return user_out(db, user)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_me(user: CurrentUser, db: Db) -> Response:
    """
    Deletes the account and, through "on delete cascade", every row about it:
    Circle, check-ins (including an active one), SOS history, photos and
    logins. Google Play requires apps with accounts to offer this.
    """
    user_id = str(user.id)
    db.delete(user)
    db.commit()
    clear_history_cache(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
