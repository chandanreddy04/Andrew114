"""Your Circle of Trust: the people texted when you miss a check-in or press SOS."""

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from app.deps import CurrentUser, Db
from app.models import Contact, User
from app.schemas import ContactIn, ContactOut

router = APIRouter(prefix="/v1/contacts", tags=["contacts"])


def _out(c: Contact) -> ContactOut:
    return ContactOut(id=c.id, name=c.name, phone=c.phone)


def _own(db: Db, user: User, contact_id: uuid.UUID) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None or contact.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


def _check_number(db: Db, user: User, phone: str, ignore_id: uuid.UUID | None = None) -> None:
    if phone == user.phone:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "That's your own number. Add someone else."
        )
    existing = db.scalar(select(Contact).where(Contact.user_id == user.id, Contact.phone == phone))
    if existing is not None and existing.id != ignore_id:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{existing.name} already has that number.")


@router.get("")
def list_contacts(user: CurrentUser, db: Db) -> list[ContactOut]:
    rows = db.scalars(
        select(Contact).where(Contact.user_id == user.id).order_by(Contact.created_at)
    )
    return [_out(c) for c in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_contact(body: ContactIn, user: CurrentUser, db: Db) -> ContactOut:
    _check_number(db, user, body.phone)
    contact = Contact(user_id=user.id, name=body.name, phone=body.phone)
    db.add(contact)
    db.commit()
    return _out(contact)


@router.put("/{contact_id}")
def update_contact(contact_id: uuid.UUID, body: ContactIn, user: CurrentUser, db: Db) -> ContactOut:
    contact = _own(db, user, contact_id)
    _check_number(db, user, body.phone, ignore_id=contact.id)
    contact.name = body.name
    contact.phone = body.phone
    db.commit()
    return _out(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(contact_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    db.delete(_own(db, user, contact_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
