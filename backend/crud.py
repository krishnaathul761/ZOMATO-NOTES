from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from models import User, Note
from schemas import UserCreate, NoteCreate, NoteUpdate


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

def create_user(db: Session, user: UserCreate) -> User:
    db_user = User(
        name=user.name,
        email=user.email,
        password=user.password,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_user(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email).first()


# ---------------------------------------------------------------------------
# Note CRUD
# ---------------------------------------------------------------------------

def create_note(db: Session, note: NoteCreate) -> Note:
    db_note = Note(
        title=note.title,
        content=note.content,
        tag=note.tag,
        severity=note.severity,
        owner_id=note.owner_id,
    )
    db.add(db_note)
    db.commit()
    db.refresh(db_note)
    return db_note


def get_note(db: Session, note_id: int) -> Optional[Note]:
    return db.query(Note).filter(Note.id == note_id).first()


def get_notes(db: Session, tag: Optional[str] = None) -> list[Note]:
    query = db.query(Note)
    if tag:
        query = query.filter(Note.tag == tag)
    return query.order_by(Note.created_at.desc()).all()


def update_note(db: Session, note_id: int, note_update: NoteUpdate) -> Optional[Note]:
    db_note = db.query(Note).filter(Note.id == note_id).first()
    if not db_note:
        return None
    update_data = note_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_note, field, value)
    db.commit()
    db.refresh(db_note)
    return db_note


def delete_note(db: Session, note_id: int) -> bool:
    db_note = db.query(Note).filter(Note.id == note_id).first()
    if not db_note:
        return False
    db.delete(db_note)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Raw SQL reporting queries
# All three use db.execute(text("...")) — NOT the ORM query builder
# ---------------------------------------------------------------------------

def report_tag_summary(db: Session) -> list[dict]:
    """Tags with more than 1 note, ordered by count descending."""
    result = db.execute(text("""
        SELECT tag, COUNT(*) AS count
        FROM notes
        WHERE tag IS NOT NULL
        GROUP BY tag
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """))
    return [{"tag": row.tag, "count": row.count} for row in result]


def report_long_notes(db: Session) -> list[dict]:
    """Notes whose content length is above the average content length across all notes."""
    result = db.execute(text("""
        SELECT id, title, content, tag, owner_id, created_at
        FROM notes
        WHERE LENGTH(content) > (
            SELECT AVG(LENGTH(content)) FROM notes
        )
        ORDER BY LENGTH(content) DESC
    """))
    rows = result.fetchall()
    return [
        {
            "id":         row.id,
            "title":      row.title,
            "content":    row.content,
            "tag":        row.tag,
            "owner_id":   row.owner_id,
            "created_at": str(row.created_at),
        }
        for row in rows
    ]


def report_user_notes(db: Session) -> list[dict]:
    """Each user with their total note count via a raw SQL JOIN."""
    result = db.execute(text("""
        SELECT u.id AS user_id, u.name, COUNT(n.id) AS note_count
        FROM users u
        LEFT JOIN notes n ON u.id = n.owner_id
        GROUP BY u.id, u.name
        ORDER BY note_count DESC
    """))
    return [
        {"user_id": row.user_id, "name": row.name, "note_count": row.note_count}
        for row in result
    ]
