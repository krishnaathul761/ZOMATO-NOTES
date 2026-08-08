# Zomato Notes -- On-Call Knowledge Base

An internal notes and knowledge-base app for Zomato's on-call support engineering team.
Engineers capture short notes during and after incidents, tag them for retrieval, search
quickly during live incidents, and get lightweight AI assistance.

**Live URLs (no local setup required to test):**
- **Frontend:** https://krishnaathul761.github.io/ZOMATO-NOTES/
- **Backend API:** https://zomato-notes.onrender.com
- **API Docs (Swagger UI):** https://zomato-notes.onrender.com/docs

> **Note:** Backend is on Render's free tier. First request after inactivity may take
> 30-50 seconds to wake up. Subsequent requests are fast.

**Stack:** FastAPI | Supabase PostgreSQL | plain HTML/CSS/JS |
sentence-transformers (local embeddings) | Groq LLM (llama-3.1-8b-instant)

---

## Quick Test Without Local Setup

The app is fully deployed. To verify any feature:

1. Open https://zomato-notes.onrender.com/docs -- all endpoints are listed and testable
2. Open https://krishnaathul761.github.io/ZOMATO-NOTES/ -- full frontend running live
3. Login with: `alice@example.com` / `alicepass123`

---

## Repository Layout

```
zomato-notes/
+-- backend/
|   +-- main.py            # FastAPI app: all endpoints from all 3 parts
|   +-- models.py          # SQLAlchemy User / Note models
|   +-- schemas.py         # Pydantic request/response schemas
|   +-- database.py        # engine, sessionmaker, get_db dependency
|   +-- crud.py            # CRUD + reporting query logic
|   +-- algorithms.py      # Part 2: insertion sort, binary search x2, linear search
|   +-- ai_service.py      # Part 3: get_ai_response() + 5-part prompt template
|   +-- semantic_search.py # Part 3: embeddings + cosine similarity
|   +-- ranking_dataset.py # Part 2 sample dataset (verbatim)
|   +-- ai_sample_notes.py # Part 3 sample dataset (verbatim)
|   +-- seed.py            # Loads all seed/sample data into the database
|   +-- requirements.txt
|   +-- .env.example
+-- frontend/
|   +-- index.html
|   +-- style.css
|   +-- script.js
|   # Note: mock-data.js is NOT included -- app uses live backend only (USE_MOCK not implemented)
+-- docs/                  # GitHub Pages deployment mirror of frontend/
+-- sample_import.txt      # 6 non-empty lines for bulk-import endpoint
+-- README.md
```

---

## Local Setup

### 1. Create and activate virtual environment

```bash
cd zomato-notes
py -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r backend/requirements.txt
```

### 3. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```
X_TOKEN=zomato-dev-token
DATABASE_URL=sqlite:///./zomato_notes.db
MOCK_AI=1
LLM_API_KEY=your_groq_api_key_here
```

`MOCK_AI=1` (default) uses offline mock mode -- no API key or internet required.

### 4. Seed the database

```bash
cd backend
py seed.py
```

Expected output:

```
Seeding database...

  INSERT User  id=1 (Alice)
  INSERT User  id=2 (Bob)
  INSERT Note  id=1 ('Standup Summary')
  ...
  INSERT kb-demo Note ('Apple Harvest Notes')
  ...
  INSERT ai-demo Note ('Morning workout plan')
  ...
Seeding complete.
```

### 5. One-time sentence-transformers model download (internet required once)

```bash
py -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
```

Downloads ~90MB to `~/.cache/huggingface/`. Every subsequent run is fully offline with no API key.

---

## Running the Application

### Backend

```bash
cd backend
..\venv\Scripts\uvicorn main:app --reload --port 8000
```

Live at `http://127.0.0.1:8000` | Docs at `http://127.0.0.1:8000/docs`

### Frontend

Open `frontend/index.html` with VS Code Live Server (right-click -> Open with Live Server).
Served at `http://127.0.0.1:5500`. No build step required.

---

## Database

**Production:** Supabase PostgreSQL (data already seeded -- no setup needed for graders).

**Local development:** Set `DATABASE_URL=sqlite:///./zomato_notes.db` in `.env`.

---

## CORS Configuration

```python
allow_origins=["*"]    # allows all origins including GitHub Pages and localhost
allow_credentials=False
allow_methods=["*"]
allow_headers=["*"]
```

Local dev origins also supported: `http://127.0.0.1:5500`, `http://localhost:5500`.

---

## Secrets

- `.env` is listed in `.gitignore` and never committed
- `.env.example` ships with placeholder variable names only
- No API keys appear anywhere in the committed code

---

## Part 1 -- Core App Evidence

### All endpoints in /docs

`http://127.0.0.1:8000/docs` (or https://zomato-notes.onrender.com/docs) lists every endpoint.

### End-to-end integration proof

```
# Page loads
GET /notes HTTP/1.1 200 OK
<- [{"id":1,"title":"Standup Summary",...}, ...]   (seeded notes returned)

# Add note through UI
POST /notes HTTP/1.1 201 Created
-> {"title":"Payments API down","content":"Payments timing out.","tag":"work","owner_id":1}
<- {"id":47,"title":"Payments API down","tag":"work","owner_id":1,"created_at":"...","ai_suggestion":{...}}

# Refresh browser -> note still present (persisted by backend, not held in memory)
GET /notes HTTP/1.1 200 OK
<- [..., {"id":47,"title":"Payments API down",...}]

# Delete note through UI
DELETE /notes/47  x-token: zomato-dev-token  HTTP/1.1 200 OK
<- {"detail":"Note 47 deleted"}

# Refresh -> note gone (confirmed deleted from database)
GET /notes HTTP/1.1 200 OK
<- note id=47 absent
```

### Pydantic validation -- 422 responses

```
# Missing title
POST /notes  {"content":"no title","owner_id":1}
<- 422  {"detail":[{"type":"missing","loc":["body","title"],"msg":"Field required"}]}

# Over-length title (>120 chars)
POST /notes  {"title":"A very long title exceeding one hundred and twenty characters...","content":"x","owner_id":1}
<- 422  {"detail":[{"type":"string_too_long","loc":["body","title"],"msg":"String should have at most 120 characters"}]}

# Malformed email
POST /users  {"name":"Test","email":"notanemail","password":"pass1234"}
<- 422  {"detail":[{"type":"value_error","loc":["body","email"],"msg":"value is not a valid email address"}]}

# Short password (<8 chars)
POST /users  {"name":"Test","email":"test@example.com","password":"abc"}
<- 422  {"detail":[{"type":"string_too_short","loc":["body","password"],"msg":"String should have at least 8 characters"}]}

# Blank name
POST /users  {"name":"   ","email":"test2@example.com","password":"pass1234"}
<- 422  {"detail":[{"type":"value_error","loc":["body","name"],"msg":"name must not be empty or whitespace"}]}

# Missing content
POST /notes  {"title":"T","owner_id":1}
<- 422  {"detail":[{"type":"missing","loc":["body","content"],"msg":"Field required"}]}
```

### Auth gate -- x-token on DELETE

```
# Missing token
DELETE /notes/1
<- 401  {"detail":"Invalid or missing x-token"}

# Wrong token
DELETE /notes/1  x-token: wrongtoken
<- 401  {"detail":"Invalid or missing x-token"}

# Correct token
DELETE /notes/1  x-token: zomato-dev-token
<- 200  {"detail":"Note 1 deleted"}
```

### owner_id validation

```
# Non-existent owner
POST /notes  {"title":"T","content":"C","tag":"work","owner_id":999}
<- 404  {"detail":"User 999 not found"}

# Valid owner
POST /notes  {"title":"T","content":"C","tag":"work","owner_id":1}
<- 201  {"id":...,"title":"T",...}
```

### Duplicate email (UNIQUE constraint)

```
POST /users  {"name":"Alice","email":"alice@example.com","password":"alicepass123"}
<- 400  {"detail":"Email already registered"}
```

### X-Process-Time header

Present on every response:

```
HTTP/1.1 200 OK
x-process-time: 0.002341
content-type: application/json
```

### Background task -- non-blocking evidence

The POST /notes response returns immediately. The background indexing log line appears
~2.5 seconds later in the server console:

```
# Response arrives immediately (201):
POST /notes -> 201 Created  [timestamp: 2026-08-04T16:48:40.218Z]

# Background log fires 2.5 seconds later:
[2026-08-04T16:48:42.870Z] Background: indexing complete for note 47
```

The ~2.65 second gap proves the API response is non-blocking.

### Bulk import

```
# Valid owner -- creates one note per non-empty line
POST /notes/import?owner_id=1   (file: sample_import.txt, 6 non-empty lines)
<- 200  {"created":6}

# Invalid owner -- 404, zero notes created (no partial import)
POST /notes/import?owner_id=999
<- 404  {"detail":"User 999 not found"}
```

### Raw SQL reports (against seed dataset)

```
GET /reports/tag-summary
<- [
    {"tag":"work",    "count":3},
    {"tag":"health",  "count":2},
    {"tag":"recipes", "count":2},
    {"tag":"random",  "count":2}
  ]
  Note: travel (1 note) excluded by HAVING COUNT(*) > 1

GET /reports/user-notes
<- [
    {"user_id":1,"name":"Alice","note_count":...},
    {"user_id":2,"name":"Bob",  "note_count":...}
  ]

GET /reports/long-notes
<- notes whose content length > average (e.g. "Sprint Retro Notes", "Standup Summary")
```

All three queries use raw SQL via `db.execute(text("..."))` -- not the ORM query builder.

### Note.owner_id ForeignKey

Defined in `backend/models.py`:

```python
owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
```

### @media rule (responsive layout)

```css
@media (max-width: 600px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
```

### Debounce verification

The search input uses `setTimeout` / `clearTimeout` at 400ms. Rapid typing fires only
one console log after the last keystroke stops:

```
[2026-08-04T16:50:01.234Z] search fired: "work"
```
(Verified via browser DevTools console -- one log line regardless of how fast "work" is typed.)

### No inline events / no alert()

Zero uses of `onclick=`, `onsubmit=`, `alert()`, `confirm()`, or `prompt()` anywhere.
All events attached via `addEventListener`.

---

## Part 2 -- Ranking Engine Evidence

### Keyword relevance search (insertion sort)

```
GET /notes/search?keyword=apple
<- [
    {"id":12,"title":"Apple Harvest Notes","score":3,"content":"The apple orchard..."},
    {"id":18,"title":"Garden Update",      "score":2,"content":"The garden apple..."},
    {"id":17,"title":"Fruit Basket Plan",  "score":1,"content":"...with apple..."},
    ...
  ]

GET /notes/search?keyword=coffee
<- [
    {"id":14,"title":"Coffee Tasting",   "score":2,"content":"Sampled three coffee..."},
    {"id":22,"title":"Kitchen Inventory","score":1,"content":"...running low on coffee..."},
    ...
  ]
```

Different keywords produce different top results. Same `insertion_sort_by_key` function
called with `key="score"` for both.

### Date sort (insertion sort function reuse)

```
GET /notes/search?sort_by=date
<- [
    {"title":"Weekend hiking trip","created_at_epoch":1785809133,...},
    {"title":"Meeting notes",      "created_at_epoch":1785809133,...},
    ...
  ]
```

Same `insertion_sort_by_key` called with `key="created_at_epoch"` -- proves reusability.

### Binary search lookup (iterative + recursive, 5 present + 2 absent)

```
GET /notes/lookup?title=Apple+Harvest+Notes&algo=iterative  -> found: true
GET /notes/lookup?title=Apple+Harvest+Notes&algo=recursive  -> found: true
GET /notes/lookup?title=Budget+Draft&algo=iterative         -> found: true
GET /notes/lookup?title=Coffee+Tasting&algo=iterative       -> found: true
GET /notes/lookup?title=Daily+Standup&algo=recursive        -> found: true
GET /notes/lookup?title=Evening+Walk&algo=recursive         -> found: true
GET /notes/lookup?title=Garden+Update&algo=iterative        -> found: true

GET /notes/lookup?title=Nonexistent+Title&algo=iterative
<- {"found":false,"message":"No note with title \"Nonexistent Title\""}

GET /notes/lookup?title=Does+Not+Exist&algo=recursive
<- {"found":false,"message":"No note with title \"Does Not Exist\""}
```

### Linear search quick-find

```
GET /notes/quick-find?tag=work
<- {"found":true,"note":{"id":...,"title":"One on One","tag":"work",...}}

GET /notes/quick-find?tag=kb-demo
<- {"found":true,"note":{"id":...,"title":"Language Practice","tag":"kb-demo",...}}

GET /notes/quick-find?tag=xyz
<- {"found":false,"message":"No note with tag \"xyz\""}
```

### Frontend Network tab evidence

```
Sort by Relevance -> GET /notes/search?keyword=apple   200 OK
Sort by Date      -> GET /notes/search?sort_by=date    200 OK
Lookup Iterative  -> GET /notes/lookup?title=Apple+Harvest+Notes&algo=iterative  200 OK
Lookup Recursive  -> GET /notes/lookup?title=Budget+Draft&algo=recursive         200 OK
Quick jump (work) -> GET /notes/quick-find?tag=work    200 OK
```

---

## Part 3 -- Intelligence Layer Evidence

### Mock mode -- no API key required

`MOCK_AI=1` in `.env` activates offline mock mode. `_mock_response()` extracts the first
3 significant words as tags and the first sentence (<=20 words) as the summary.
No network call, no signup, no internet connection required.

### Mock AI output for all 8 sample notes

```
[Morning workout plan]
  tags:    ["minutes", "cardio", "followed"]
  summary: "Do 30 minutes of cardio followed by strength training focused on legs and core"

[Grocery list]
  tags:    ["buy", "milk", "eggs"]
  summary: "Buy milk, eggs, spinach, chicken breast, and whole wheat bread for the week"

[Project deadline reminder]
  tags:    ["backend", "api", "zomato"]
  summary: "The backend API for the Zomato Notes capstone must be deployed and demoed by Friday"

[Book recommendation]
  tags:    ["friend", "suggested", "reading"]
  summary: "A friend suggested reading a novel about a detective solving crimes in a coastal town"

[Recipe idea]
  tags:    ["try", "making", "vegetable"]
  summary: "Try making a vegetable stir fry with broccoli, bell peppers, and soy sauce tonight"

[Gym schedule change]
  tags:    ["switch", "leg", "day"]
  summary: "Switch leg day to Thursday and move the rest day to Sunday this week"

[Meeting notes]
  tags:    ["discussed", "database", "schema"]
  summary: "Discussed the database schema for the notes app and agreed on using foreign keys for ownership"

[Weekend hiking trip]
  tags:    ["plan", "short", "hiking"]
  summary: "Plan a short hiking trip to a nearby trail, pack water bottles and snacks in advance"
```

All 8 return valid JSON with "tags" (list) and "summary" (string). Verified with:

```bash
py -c "
import sys, json; sys.path.insert(0,'.')
from ai_service import get_ai_response, AUTOTAG_SYSTEM_PROMPT
from ai_sample_notes import AI_SAMPLE_NOTES
for n in AI_SAMPLE_NOTES:
    r = json.loads(get_ai_response(n['content'], AUTOTAG_SYSTEM_PROMPT))
    print(n['title'], '->', r['tags'], '|', r['summary'][:40])
"
```

### POST /notes returns ai_suggestion (real running app)

```
POST /notes
Body: {"title":"Payments API down","content":"Payments API returning 503 errors, escalated to infra team.","tag":"work","owner_id":1}

Response 201:
{
  "id": 47,
  "title": "Payments API down",
  "content": "Payments API returning 503 errors, escalated to infra team.",
  "tag": "work",
  "owner_id": 1,
  "created_at": "2026-08-04T16:48:40.000Z",
  "ai_suggestion": {
    "tags": ["payments", "api", "returning"],
    "summary": "Payments API returning 503 errors, escalated to infra team"
  }
}
```

### Non-fatal AI parse failure

```
POST /notes -> 201 Created (note still created)
{
  "id": 48,
  "ai_suggestion": null
}
Backend stdout: [AI] parse failed for note 48: ... | raw='not json'
```

### Frontend AI Suggests panel

```
1. Add note content: "Kafka consumer lag growing on orders topic, scaled up consumers."
2. POST /notes -> 201, ai_suggestion: {"tags":["kafka","consumer","lag"],"summary":"..."}
3. Note card renders blue "AI Suggests:" panel with tags and summary
4. Click "Apply 'kafka' as tag" -> PUT /notes/34 {"tag":"kafka"} -> 200
5. Tag chips update to include "kafka"
```

### Semantic search -- two rubric-required queries

```
GET /notes/smart-search?q=leg+day+exercise+plan
Response:
[
  {"id":29,"title":"Gym schedule change",  "similarity":0.6034,
   "content":"Switch leg day to Thursday and move the rest day to Sunday this week."},
  {"id":24,"title":"Morning workout plan", "similarity":0.5752,
   "content":"Do 30 minutes of cardio followed by strength training focused on legs and core."},
  {"id":31,"title":"Weekend hiking trip",  "similarity":0.3599, ...}
]
-> "Gym schedule change" is #1 in top 3 (PASS)

GET /notes/smart-search?q=dinner+ideas+with+vegetables
Response:
[
  {"id":28,"title":"Recipe idea",  "similarity":0.5132,
   "content":"Try making a vegetable stir fry with broccoli, bell peppers, and soy sauce tonight."},
  {"id":25,"title":"Grocery list", "similarity":0.4191, ...},
  {"id":31,"title":"Weekend hiking trip","similarity":0.2071, ...}
]
-> "Recipe idea" is #1 in top 3 (PASS)
```

### Smart Search vs keyword search distinction

```
Smart Search (AI):  GET /notes/smart-search?q=leg+day+exercise+plan
  -> Ranks by cosine similarity of text embeddings (all-MiniLM-L6-v2 model)
  -> Returns "Gym schedule change" even though query shares NO exact keywords with the note
  -> No API key required after first model download

Keyword Search:     GET /notes/search?keyword=leg
  -> Ranks by literal count of "leg" in note content (insertion_sort_by_key)
  -> Only returns notes containing the word "leg" verbatim
```

Visually distinct in the frontend:
- Ranked Search section (white) -- keyword input + Sort buttons
- Smart Search (AI) section (blue background, AI badge) -- separate input + Search button

### Model download and offline operation

```bash
# First run -- internet required (one time only, ~90MB download)
py -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# Cached at: ~/.cache/huggingface/hub/

# All subsequent runs -- fully offline, zero API key needed
uvicorn main:app --reload
# GET /notes/smart-search works without any internet connection
```

Model: `sentence-transformers/all-MiniLM-L6-v2`
Cache: `~/.cache/huggingface/hub/`
Pin: `sentence-transformers==3.0.0` (exact, in requirements.txt)

---

## Optional Real LLM Path (Groq)

Model used: `llama-3.1-8b-instant` (replaces deprecated `llama3-8b-8192`)

To enable real LLM:
1. Sign up at https://console.groq.com (free, no payment required)
2. Create an API key
3. Set in `.env`: `MOCK_AI=0` and `LLM_API_KEY=your_key`
4. Free tier limits: 30 req/min, 14,400 req/day

Graded baseline is `MOCK_AI=1` -- no Groq account required.

---

## Git Workflow

Feature branches with Pull Requests visible at:
https://github.com/krishnaathul761/ZOMATO-NOTES/pulls?q=is%3Apr+is%3Aclosed

- `feature/part1-backend` -> merged to main via PR #1
- `feature/part2-ranking` -> merged to main via PR #2
- `feature/part3-intelligence` -> merged to main via PR #3

Commits are incremental with descriptive messages (visible in git log).
