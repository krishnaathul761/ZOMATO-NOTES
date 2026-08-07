"""
seed.py — Idempotent seeder for Zomato Notes.
Run from the backend/ directory:
    ..\venv\Scripts\python seed.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import SessionLocal, engine
from models import Base, User, Note
from ranking_dataset import RANKING_DATASET
from ai_sample_notes import AI_SAMPLE_NOTES
from sqlalchemy import text

# Create tables if they don't exist yet
Base.metadata.create_all(bind=engine)

# ---------------------------------------------------------------------------
# Seed data (verbatim from the problem statement)
# ---------------------------------------------------------------------------
SEED_USERS = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "password": "alicepass123"},
    {"id": 2, "name": "Bob",   "email": "bob@example.com",   "password": "bobpass123"},
]

SEED_NOTES = [
    {"id": 1,  "owner_id": 1, "title": "Standup Summary",    "tag": "work",
     "content": "Discussed sprint progress, blockers on the payments API integration, and the plan for the demo on Friday."},
    {"id": 2,  "owner_id": 1, "title": "Sprint Retro Notes", "tag": "work",
     "content": "Retro highlighted communication gaps between frontend and backend teams and agreed on daily syncs going forward."},
    {"id": 3,  "owner_id": 2, "title": "One on One",         "tag": "work",
     "content": "Quick check-in, no blockers, discussed career growth goals for next quarter."},
    {"id": 4,  "owner_id": 1, "title": "Morning Run",        "tag": "health",
     "content": "Ran 5km along the river trail before breakfast, felt great."},
    {"id": 5,  "owner_id": 2, "title": "Doctor Visit",       "tag": "health",
     "content": "Annual checkup went well, blood pressure normal, scheduled next visit in six months."},
    {"id": 6,  "owner_id": 1, "title": "Pasta Recipe",       "tag": "recipes",
     "content": "Boil pasta, saute garlic in olive oil, add tomatoes, basil, and a pinch of chili flakes."},
    {"id": 7,  "owner_id": 2, "title": "Smoothie Recipe",    "tag": "recipes",
     "content": "Blend banana, spinach, almond milk, and a spoon of peanut butter for breakfast."},
    {"id": 8,  "owner_id": 1, "title": "Flight Booking",     "tag": "travel",
     "content": "Booked a round trip flight for the December vacation, window seat confirmed."},
    {"id": 9,  "owner_id": 2, "title": "Random Thought",     "tag": "random",
     "content": "Maybe the library needs a better recommendation system based on reading history."},
    {"id": 10, "owner_id": 1, "title": "Quote To Remember",  "tag": "random",
     "content": "Done is better than perfect, keep shipping."},
]


def reset_sequences(db):
    """
    After inserting rows with explicit IDs into PostgreSQL, the autoincrement
    sequence is out of sync. This resets both sequences to the current max id
    so subsequent autoincrement inserts don't collide.
    Only runs on PostgreSQL — SQLite doesn't use sequences.
    """
    url = str(engine.url)
    if not url.startswith("postgresql"):
        return
    try:
        db.execute(text(
            "SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 0) + 1, false)"
        ))
        db.execute(text(
            "SELECT setval('notes_id_seq', COALESCE((SELECT MAX(id) FROM notes), 0) + 1, false)"
        ))
        db.commit()
        print("  Sequences reset to current max IDs")
    except Exception as e:
        db.rollback()
        print(f"  Sequence reset skipped: {e}")


# ---------------------------------------------------------------------------
# Seed logic — idempotent (safe to run multiple times)
# ---------------------------------------------------------------------------
def seed():
    db = SessionLocal()
    try:
        # --- Users ---
        for u in SEED_USERS:
            try:
                exists = db.query(User).filter(User.id == u["id"]).first()
                if exists:
                    print(f"  SKIP  User  id={u['id']} ({u['name']}) — already exists")
                else:
                    db.add(User(
                        id=u["id"],
                        name=u["name"],
                        email=u["email"],
                        password=u["password"],
                    ))
                    db.commit()
                    print(f"  INSERT User  id={u['id']} ({u['name']})")
            except Exception as e:
                db.rollback()
                print(f"  SKIP  User  id={u['id']} — {e.__class__.__name__}")

        # --- Notes ---
        for n in SEED_NOTES:
            try:
                exists = db.query(Note).filter(Note.id == n["id"]).first()
                if exists:
                    print(f"  SKIP  Note  id={n['id']} ({n['title']!r}) — already exists")
                else:
                    db.add(Note(
                        id=n["id"],
                        owner_id=n["owner_id"],
                        title=n["title"],
                        tag=n["tag"],
                        content=n["content"],
                    ))
                    db.commit()
                    print(f"  INSERT Note  id={n['id']} ({n['title']!r})")
            except Exception as e:
                db.rollback()
                print(f"  SKIP  Note  id={n['id']} — {e.__class__.__name__}")

        # Reset sequences BEFORE autoincrement inserts
        reset_sequences(db)

        # --- RANKING_DATASET (Phase 3) — tag: kb-demo, owner_id: 1 ---
        for n in RANKING_DATASET:
            try:
                exists = db.query(Note).filter(
                    Note.title == n["title"], Note.owner_id == 1
                ).first()
                if exists:
                    print(f"  SKIP  kb-demo Note ({n['title']!r}) — already exists")
                else:
                    db.add(Note(
                        owner_id=1,
                        title=n["title"],
                        tag="kb-demo",
                        content=n["content"],
                    ))
                    db.commit()
                    print(f"  INSERT kb-demo Note ({n['title']!r})")
            except Exception as e:
                db.rollback()
                print(f"  SKIP  kb-demo Note ({n['title']!r}) — {e.__class__.__name__}")

        # --- AI_SAMPLE_NOTES (Phase 4) — tag: ai-demo, owner_id: 2 ---
        for n in AI_SAMPLE_NOTES:
            try:
                exists = db.query(Note).filter(
                    Note.title == n["title"], Note.owner_id == 2
                ).first()
                if exists:
                    print(f"  SKIP  ai-demo Note ({n['title']!r}) — already exists")
                else:
                    db.add(Note(
                        owner_id=2,
                        title=n["title"],
                        tag="ai-demo",
                        content=n["content"],
                    ))
                    db.commit()
                    print(f"  INSERT ai-demo Note ({n['title']!r})")
            except Exception as e:
                db.rollback()
                print(f"  SKIP  ai-demo Note ({n['title']!r}) — {e.__class__.__name__}")

        print("\nSeeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding database...\n")
    seed()
