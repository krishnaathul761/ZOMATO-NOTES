import asyncio
import os
import time
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

import crud
import models
import schemas
from database import engine, get_db
from algorithms import (
    insertion_sort_by_key,
    binary_search_iterative,
    binary_search_recursive,
    linear_search,
)
from ai_service import get_ai_response, AUTOTAG_SYSTEM_PROMPT
from semantic_search import semantic_search as run_semantic_search
from sqlalchemy import asc
import json

load_dotenv()

# ---------------------------------------------------------------------------
# Create all tables on startup â€” non-fatal if DB is temporarily unreachable
# ---------------------------------------------------------------------------
try:
    models.Base.metadata.create_all(bind=engine)
    print("[DB] Tables created/verified successfully")
except Exception as e:
    print(f"[DB] Warning: could not create tables on startup: {e}")
    print("[DB] Tables will be created on first successful DB connection")

# ---------------------------------------------------------------------------
# App instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Zomato Notes API",
    description="Internal knowledge-base for on-call support engineers.",
    version="1.1.0",
)

# ---------------------------------------------------------------------------
# CORS â€” allow the frontend dev server origins
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# X-Process-Time middleware â€” on every response
# ---------------------------------------------------------------------------
@app.middleware("http")
async def add_process_time_header(request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(round(time.time() - start, 6))
    return response

# ---------------------------------------------------------------------------
# Auth dependency â€” used only on DELETE /notes/{id}
# ---------------------------------------------------------------------------
X_TOKEN = os.getenv("X_TOKEN", "supersecret")

def verify_token(x_token: Optional[str] = Header(default=None)):
    if not x_token or x_token != X_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing x-token")

# ---------------------------------------------------------------------------
# Background task â€” simulates a 2-3 s indexing step
# ---------------------------------------------------------------------------
async def fake_index_task(note_id: int):
    await asyncio.sleep(2.5)
    print(
        f"[{datetime.utcnow().isoformat()}] Background: indexing complete for note {note_id}"
    )

# ===========================================================================
# USER ENDPOINTS
# ===========================================================================

@app.post("/users", response_model=schemas.UserResponse, status_code=201, tags=["Users"])
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Create a new user. Email must be unique."""
    existing = crud.get_user_by_email(db, user.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db, user)


@app.get("/users", response_model=list[schemas.UserResponse], tags=["Users"])
def list_users(db: Session = Depends(get_db)):
    """List all registered authors/engineers."""
    return db.query(models.User).order_by(models.User.id).all()


@app.post("/login", tags=["Users"])
def login(payload: dict, db: Session = Depends(get_db)):
    """
    Authenticate an author by email + password.
    Returns the user object on success, 401 on wrong credentials.
    Note: passwords are stored as plaintext (demo only — not production practice).
    """
    email    = payload.get("email", "").strip().lower()
    password = payload.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = crud.get_user_by_email(db, email)
    if not user or user.password != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"id": user.id, "name": user.name, "email": user.email}


@app.put("/users/{user_id}", tags=["Users"])
def update_user(user_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Update a user's name and/or password.
    Requires current_password to verify identity before any change.
    """
    current_password = payload.get("current_password", "")
    new_name         = payload.get("name", "").strip()
    new_password     = payload.get("new_password", "").strip()

    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password != current_password:
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if not new_name and not new_password:
        raise HTTPException(status_code=400, detail="Provide name or new_password to update")
    if new_name:
        if not new_name:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
        user.name = new_name
    if new_password:
        if len(new_password) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters")
        user.password = new_password
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email}


@app.delete("/users/{user_id}", tags=["Users"])
def delete_user(user_id: int, payload: dict, db: Session = Depends(get_db)):
    """
    Delete a user account and all their notes.
    Requires password confirmation.
    """
    password = payload.get("password", "")
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.password != password:
        raise HTTPException(status_code=401, detail="Password is incorrect")
    db.delete(user)
    db.commit()
    return {"detail": f"User {user.name} deleted successfully"}


# ===========================================================================
# NOTE ENDPOINTS
# NOTE: specific paths (/import, /search, /lookup, /quick-find, /smart-search)
# MUST be declared before the parameterised /notes/{id} route so FastAPI does
# not swallow them as an id value.
# ===========================================================================

# ---------------------------------------------------------------------------
# POST /notes/import  â€” bulk import from .txt file
# ---------------------------------------------------------------------------
@app.post("/notes/import", tags=["Notes"])
async def import_notes(
    owner_id: int = Query(..., description="ID of the owner for all imported notes"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Import notes from a plain-text file.  Every non-empty line becomes one Note.
    The owner_id must exist in the User table; otherwise a 404 is returned and
    zero notes are created.
    """
    owner = crud.get_user(db, owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {owner_id} not found")

    content_bytes = await file.read()
    lines = content_bytes.decode("utf-8").splitlines()

    created_count = 0
    for line in lines:
        line = line.strip()
        if not line:
            continue
        note_in = schemas.NoteCreate(
            title=line[:60],
            content=line,
            tag="imported",
            owner_id=owner_id,
        )
        crud.create_note(db, note_in)
        created_count += 1

    return {"created": created_count}


# ---------------------------------------------------------------------------
# POST /notes
# ---------------------------------------------------------------------------
@app.post("/notes", response_model=schemas.NoteResponse, status_code=201, tags=["Notes"])
async def create_note(
    note: schemas.NoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Create a note.  owner_id must reference an existing User.
    Registers a background indexing task that fires after the response is sent.
    """
    owner = crud.get_user(db, note.owner_id)
    if not owner:
        raise HTTPException(status_code=404, detail=f"User {note.owner_id} not found")

    db_note = crud.create_note(db, note)

    # Fire-and-forget indexing simulation
    background_tasks.add_task(fake_index_task, db_note.id)

    # --- Phase 4: AI auto-tagging ---
    # Call get_ai_response server-side; parse the JSON suggestion.
    # json.loads failures are caught and logged â€” note is still created with ai_suggestion=null.
    ai_suggestion = None
    raw = None
    try:
        raw = get_ai_response(db_note.content, AUTOTAG_SYSTEM_PROMPT)
        ai_suggestion = json.loads(raw)   # {"tags": [...], "summary": "..."}
    except Exception as exc:
        print(f"[AI] parse failed for note {db_note.id}: {exc!r} | raw={raw!r}")
        ai_suggestion = None

    response_data = schemas.NoteResponse.model_validate(db_note)
    # Attach ai_suggestion to the response (not persisted to DB â€” returned in response only)
    result = response_data.model_dump()
    result["ai_suggestion"] = ai_suggestion
    return result


# ---------------------------------------------------------------------------
# GET /notes/search  â€” keyword relevance OR date sort (Phase 3)
# MUST be declared before /notes/{id}
# ---------------------------------------------------------------------------
@app.get("/notes/search", tags=["Ranking"])
def search_notes(
    keyword: Optional[str] = Query(default=None),
    sort_by: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Phase 3 â€” Ranking Engine.
    ?keyword=<value>  â†’ top 5 notes sorted by keyword-occurrence score (insertion sort).
    ?sort_by=date     â†’ all notes sorted descending by creation time (same sort fn, different key).
    """
    notes = crud.get_notes(db)
    note_dicts = [
        {
            "id":               n.id,
            "title":            n.title,
            "content":          n.content,
            "tag":              n.tag,
            "owner_id":         n.owner_id,
            "created_at":       n.created_at.isoformat(),
            "created_at_epoch": int(n.created_at.timestamp()),
        }
        for n in notes
    ]

    if keyword:
        kw = keyword.lower()
        for nd in note_dicts:
            nd["score"] = nd["content"].lower().count(kw)
        sorted_notes = insertion_sort_by_key(note_dicts, key="score")
        return sorted_notes[:5]

    if sort_by == "date":
        sorted_notes = insertion_sort_by_key(note_dicts, key="created_at_epoch")
        return sorted_notes

    raise HTTPException(status_code=400, detail="Provide ?keyword=<value> or ?sort_by=date")


# ---------------------------------------------------------------------------
# GET /notes/lookup  â€” exact title binary search (Phase 3)
# MUST be declared before /notes/{id}
# ---------------------------------------------------------------------------
@app.get("/notes/lookup", tags=["Ranking"])
def lookup_note(
    title: str = Query(...),
    algo: str  = Query(default="iterative"),
    db: Session = Depends(get_db),
):
    """
    Phase 3 â€” Binary search for an exact title match.
    DB is sorted ORDER BY title ASC at the SQL level.
    algo=iterative (default) or algo=recursive.
    """
    notes_ordered = db.query(models.Note).order_by(asc(models.Note.title)).all()
    sorted_titles = [n.title for n in notes_ordered]

    if algo == "recursive":
        idx = binary_search_recursive(sorted_titles, title, 0, len(sorted_titles) - 1)
    else:
        idx = binary_search_iterative(sorted_titles, title)

    if idx == -1:
        return {"found": False, "message": f'No note with title "{title}"'}

    n = notes_ordered[idx]
    return {
        "found": True,
        "note": {
            "id": n.id, "title": n.title,
            "content": n.content, "tag": n.tag,
            "owner_id": n.owner_id, "created_at": n.created_at.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# GET /notes/quick-find  â€” linear search by tag (Phase 3)
# MUST be declared before /notes/{id}
# ---------------------------------------------------------------------------
@app.get("/notes/quick-find", tags=["Ranking"])
def quick_find_note(
    tag: str = Query(...),
    db: Session  = Depends(get_db),
):
    """
    Phase 3 â€” Linear search (found-flag pattern) for first note matching a tag.
    Returns found: false (not a 500) when no note with that tag exists.
    """
    notes = crud.get_notes(db)
    note_dicts = [
        {
            "id": n.id, "title": n.title,
            "content": n.content, "tag": n.tag,
            "owner_id": n.owner_id, "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]
    result = linear_search(note_dicts, key="tag", value=tag)
    if result is None:
        return {"found": False, "message": f'No note with tag "{tag}"'}
    return {"found": True, "note": result}


# ---------------------------------------------------------------------------
# GET /notes/smart-search  â€” semantic search via embeddings (Phase 4)
# MUST be declared before /notes/{id}
# ---------------------------------------------------------------------------
@app.get("/notes/smart-search", tags=["Intelligence"])
def smart_search_notes(
    q: str = Query(..., description="Natural language query"),
    db: Session = Depends(get_db),
):
    """
    Phase 4 â€” Semantic search over the ai-demo dataset using
    sentence-transformers/all-MiniLM-L6-v2 + cosine similarity.
    Returns top 3 notes ranked by semantic similarity.
    Fully offline after the one-time model download.
    """
    notes = crud.get_notes(db, tag="ai-demo")
    note_dicts = [
        {
            "id":       n.id,
            "title":    n.title,
            "content":  n.content,
            "tag":      n.tag,
            "owner_id": n.owner_id,
            "created_at": n.created_at.isoformat(),
        }
        for n in notes
    ]
    results = run_semantic_search(query=q, notes=note_dicts, top_k=3)
    return results


# ---------------------------------------------------------------------------
# GET /notes  (list, optional ?tag= filter)
# ---------------------------------------------------------------------------
@app.get("/notes", response_model=list[schemas.NoteResponse], tags=["Notes"])
def list_notes(tag: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    """List all notes. Filter by tag with ?tag=<value>."""
    return crud.get_notes(db, tag=tag)


# ---------------------------------------------------------------------------
# GET /notes/{id}
# ---------------------------------------------------------------------------
@app.get("/notes/{note_id}", response_model=schemas.NoteResponse, tags=["Notes"])
def get_note(note_id: int, db: Session = Depends(get_db)):
    """Retrieve a single note by ID."""
    db_note = crud.get_note(db, note_id)
    if not db_note:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    return db_note


# ---------------------------------------------------------------------------
# PUT /notes/{id}
# ---------------------------------------------------------------------------
@app.put("/notes/{note_id}", response_model=schemas.NoteResponse, tags=["Notes"])
def update_note(
    note_id: int,
    note_update: schemas.NoteUpdate,
    db: Session = Depends(get_db),
):
    """Update title, content, and/or tag of an existing note."""
    updated = crud.update_note(db, note_id, note_update)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    return updated


# ---------------------------------------------------------------------------
# DELETE /notes/{id}  â€” requires x-token header
# ---------------------------------------------------------------------------
@app.delete("/notes/{note_id}", tags=["Notes"])
def delete_note(
    note_id: int,
    db: Session = Depends(get_db),
    _token: None = Depends(verify_token),
):
    """
    Delete a note.  Requires the correct x-token header.
    Returns 401 if the token is missing or wrong, 404 if the note does not exist.
    """
    deleted = crud.delete_note(db, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Note {note_id} not found")
    return {"detail": f"Note {note_id} deleted"}


# ===========================================================================
# REPORTING ENDPOINTS
# ===========================================================================

@app.get("/reports/tag-summary", tags=["Reports"])
def tag_summary(db: Session = Depends(get_db)):
    """
    Raw SQL: tags with more than 1 note and their counts.
    travel (1 note in seed) must be absent from results.
    """
    return crud.report_tag_summary(db)


@app.get("/reports/long-notes", tags=["Reports"])
def long_notes(db: Session = Depends(get_db)):
    """
    Raw SQL: notes whose content length exceeds the average content length
    across all notes (uses a subquery).
    """
    return crud.report_long_notes(db)


@app.get("/reports/user-notes", tags=["Reports"])
def user_notes(db: Session = Depends(get_db)):
    """
    Raw SQL: each user with their total note count (JOIN + GROUP BY).
    """
    return crud.report_user_notes(db)
