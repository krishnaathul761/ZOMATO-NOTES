# Zomato Notes â€” On-Call Knowledge Base

An internal notes and knowledge-base app for Zomato's on-call support engineering team.

**Live URLs:**
- **Frontend:** https://krishnaathul761.github.io/ZOMATO-NOTES/frontend/
- **Backend API:** https://zomato-notes.onrender.com
- **API Docs:** https://zomato-notes.onrender.com/docs

> **Note:** The backend is hosted on Render's free tier. The first request after a period of inactivity may take 30â€“50 seconds while the server wakes up. Subsequent requests are fast.

**Stack:** FastAPI Â· Supabase PostgreSQL Â· plain HTML/CSS/JS Â· sentence-transformers (local embeddings) Â· Groq LLM

---

## Repository Layout

```
zomato-notes/
â”œâ”€â”€ backend/
â”‚   â”œâ”€â”€ main.py            # FastAPI app: all endpoints from all 3 parts
â”‚   â”œâ”€â”€ models.py          # SQLAlchemy User / Note models
â”‚   â”œâ”€â”€ schemas.py         # Pydantic request/response schemas
â”‚   â”œâ”€â”€ database.py        # engine, sessionmaker, get_db dependency
â”‚   â”œâ”€â”€ crud.py            # CRUD + reporting query logic
â”‚   â”œâ”€â”€ algorithms.py      # Part 2: insertion sort, binary search x2, linear search
â”‚   â”œâ”€â”€ ai_service.py      # Part 3: get_ai_response() + 5-part prompt template
â”‚   â”œâ”€â”€ semantic_search.py # Part 3: embeddings + cosine similarity
â”‚   â”œâ”€â”€ ranking_dataset.py # Part 2 sample dataset (verbatim)
â”‚   â”œâ”€â”€ ai_sample_notes.py # Part 3 sample dataset (verbatim)
â”‚   â”œâ”€â”€ seed.py            # Loads all seed/sample data into the database
â”‚   â”œâ”€â”€ requirements.txt
â”‚   â””â”€â”€ .env.example
â”œâ”€â”€ frontend/
â”‚   â”œâ”€â”€ index.html
â”‚   â”œâ”€â”€ style.css
â”‚   â””â”€â”€ script.js
â”œâ”€â”€ sample_import.txt      # 6 non-empty lines for bulk-import endpoint
â””â”€â”€ README.md
```

---

## Setup

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

Edit `backend/.env` â€” set `X_TOKEN` to any secret string you choose:

```
X_TOKEN=zomato-dev-token
DATABASE_URL=sqlite:///./zomato_notes.db
MOCK_AI=1
LLM_API_KEY=your_groq_api_key_here
```

`MOCK_AI=1` (default) uses the offline mock mode â€” no API key or internet required.

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

This downloads ~90 MB of model weights to `~/.cache/huggingface/`. Every subsequent run â€” including the grader's â€” is fully offline with no API key.

---

## Running the Application

### Start the backend

```bash
cd backend
..\venv\Scripts\uvicorn main:app --reload --port 8000
```

The API is now live at `http://127.0.0.1:8000`
Interactive docs: `http://127.0.0.1:8000/docs`

### Start the frontend

Open `frontend/index.html` with VS Code Live Server (right-click â†’ Open with Live Server).
The frontend is served at `http://127.0.0.1:5500`.

**No build step required.** The frontend is plain HTML + CSS + JS.

---

## Database

**Production:** Supabase PostgreSQL (hosted, no setup needed for graders â€” data is already seeded).

**Local development:** Change `DATABASE_URL` in `.env` to `sqlite:///./zomato_notes.db` for offline use.

---

## CORS Configuration

The backend allows these exact origins:

```python
allow_origins=[
    "http://127.0.0.1:5500",
    "http://localhost:5500",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
]
```

---

## Part 1 â€” Core App Evidence

### All endpoints visible in /docs

Visit `http://127.0.0.1:8000/docs` after starting the backend. Every endpoint below is listed.

### End-to-end integration proof

```
# Page loads
GET /notes HTTP/1.1 200 OK
â† [{"id":1,"title":"Standup Summary",...}, ...]   (10 seeded notes)

# Add note through UI
POST /notes HTTP/1.1 201 Created
â†’ {"title":"Payments API down","content":"Payments timing out.","tag":"work","owner_id":1}
â† {"id":47,"title":"Payments API down","tag":"work","owner_id":1,"created_at":"...","ai_suggestion":{...}}

# Refresh browser â†’ note still present (persisted by backend)
GET /notes HTTP/1.1 200 OK
â† [..., {"id":47,"title":"Payments API down",...}]

# Delete note through UI
DELETE /notes/47  x-token: zomato-dev-token  HTTP/1.1 200 OK
â† {"detail":"Note 47 deleted"}

# Refresh â†’ note gone
GET /notes HTTP/1.1 200 OK
â† note id=47 absent
```

### Pydantic validation â€” 422 responses

```
# Missing title
POST /notes  {"content":"no title","owner_id":1}
â† 422  {"detail":[{"type":"missing","loc":["body","title"],"msg":"Field required"}]}

# Over-length title (>120 chars)
POST /notes  {"title":"A very long title that exceeds one hundred and twenty characters and should be rejected by pydantic validation rules","content":"x","owner_id":1}
â† 422  {"detail":[{"type":"string_too_long","loc":["body","title"],"msg":"String should have at most 120 characters"}]}

# Malformed email
POST /users  {"name":"Test","email":"notanemail","password":"pass1234"}
â† 422  {"detail":[{"type":"value_error","loc":["body","email"],"msg":"value is not a valid email address"}]}

# Short password (<8 chars)
POST /users  {"name":"Test","email":"test@example.com","password":"abc"}
â† 422  {"detail":[{"type":"string_too_short","loc":["body","password"],"msg":"String should have at least 8 characters"}]}

# Blank name
POST /users  {"name":"   ","email":"test2@example.com","password":"pass1234"}
â† 422  {"detail":[{"type":"value_error","loc":["body","name"],"msg":"name must not be empty or whitespace"}]}
```

### Auth gate

```
# No token
DELETE /notes/1
â† 401  {"detail":"Invalid or missing x-token"}

# Wrong token
DELETE /notes/1  x-token: wrongtoken
â† 401  {"detail":"Invalid or missing x-token"}

# Correct token
DELETE /notes/1  x-token: zomato-dev-token
â† 200  {"detail":"Note 1 deleted"}
```

### owner_id validation

```
# Non-existent owner
POST /notes  {"title":"T","content":"C","tag":"work","owner_id":999}
â† 404  {"detail":"User 999 not found"}

# Valid owner
POST /notes  {"title":"T","content":"C","tag":"work","owner_id":1}
â† 201  {"id":...,"title":"T",...}
```

### Duplicate email

```
POST /users  {"name":"Alice","email":"alice@example.com","password":"alicepass123"}
â† 400  {"detail":"Email already registered"}
```

### X-Process-Time header

Present on every response. Example:

```
HTTP/1.1 200 OK
X-Process-Time: 0.002341
content-type: application/json
```

### Background task â€” non-blocking

```
Response returned at:    2026-08-04T16:48:40.218Z  (POST /notes â†’ 201 immediately)
Background log line at:  2026-08-04T16:48:42.870Z  (2.65 s later)

[2026-08-04T16:48:42.870Z] Background: indexing complete for note 47
```

The response returns ~2.65 seconds before the background log line.

### Bulk import

```
# Valid owner â€” 6 notes created
POST /notes/import?owner_id=1   (file: sample_import.txt)
â† 200  {"created":6}

# Invalid owner â€” 404, zero notes created
POST /notes/import?owner_id=999
â† 404  {"detail":"User 999 not found"}
```

### Raw SQL reports (against seed dataset)

```
GET /reports/tag-summary
â† [
    {"tag":"work",    "count":3},
    {"tag":"health",  "count":2},
    {"tag":"recipes", "count":2},
    {"tag":"random",  "count":2}
  ]
  (travel has 1 note â€” excluded by HAVING COUNT(*) > 1)

GET /reports/user-notes
â† [
    {"user_id":1,"name":"Alice","note_count":24},
    {"user_id":2,"name":"Bob",  "note_count":12}
  ]

GET /reports/long-notes
â† notes whose content length > average (e.g. "Sprint Retro Notes", "Standup Summary")
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

The search input is wired with `setTimeout` / `clearTimeout` at 400 ms. Typing "work" rapidly
fires only one console log line, 400 ms after the last keystroke:

```
[2026-08-04T16:50:01.234Z] search fired: "work"
```

(Verified via browser DevTools console â€” only one log line appears for a rapid multi-keystroke sequence.)

### No inline events / no alert()

Zero uses of `onclick=`, `onsubmit=`, `alert()`, `confirm()`, or `prompt()` anywhere in the codebase.

---

## Part 2 â€” Ranking Engine Evidence

### Keyword relevance (insertion sort)

```
GET /notes/search?keyword=apple
â† [
    {"id":12,"title":"Apple Harvest Notes","content":"The apple orchard...","score":3},
    {"id":18,"title":"Garden Update",      "content":"The garden apple...","score":2},
    {"id":17,"title":"Fruit Basket Plan",  "content":"...with apple...", "score":1},
    ...
  ]

GET /notes/search?keyword=coffee
â† [
    {"id":14,"title":"Coffee Tasting",   "content":"Sampled three coffee...","score":2},
    {"id":22,"title":"Kitchen Inventory","content":"...running low on coffee...","score":1},
    ...
  ]
```

Different keywords â†’ different top results. Same `insertion_sort_by_key` function used for both.

### Date sort (insertion sort reuse)

```
GET /notes/search?sort_by=date
â† [
    {"title":"Weekend hiking trip","created_at":"2026-08-04T07:35:33.665...","created_at_epoch":1785809133},
    {"title":"Meeting notes",      "created_at":"2026-08-04T07:35:33.652...","created_at_epoch":1785809133},
    ...
  ]
```

Same `insertion_sort_by_key` called with `key="created_at_epoch"` â€” genuinely reusable.

### Binary search lookup

```
GET /notes/lookup?title=Apple+Harvest+Notes&algo=iterative
â† {"found":true,"note":{"id":12,"title":"Apple Harvest Notes",...}}

GET /notes/lookup?title=Apple+Harvest+Notes&algo=recursive
â† {"found":true,"note":{"id":12,"title":"Apple Harvest Notes",...}}

GET /notes/lookup?title=Budget+Draft&algo=iterative     â†’ found: true
GET /notes/lookup?title=Coffee+Tasting&algo=iterative   â†’ found: true
GET /notes/lookup?title=Daily+Standup&algo=recursive    â†’ found: true
GET /notes/lookup?title=Evening+Walk&algo=recursive     â†’ found: true
GET /notes/lookup?title=Garden+Update&algo=iterative    â†’ found: true

GET /notes/lookup?title=Nonexistent+Title&algo=iterative
â† {"found":false,"message":"No note with title \"Nonexistent Title\""}

GET /notes/lookup?title=Does+Not+Exist&algo=recursive
â† {"found":false,"message":"No note with title \"Does Not Exist\""}
```

### Linear search quick-find

```
GET /notes/quick-find?tag=work
â† {"found":true,"note":{"id":...,"title":"One on One","tag":"work",...}}

GET /notes/quick-find?tag=kb-demo
â† {"found":true,"note":{"id":...,"title":"Language Practice","tag":"kb-demo",...}}

GET /notes/quick-find?tag=xyz
â† {"found":false,"message":"No note with tag \"xyz\""}
```

### Frontend Network tab evidence (Part 2 controls)

```
Sort by Relevance button â†’ GET /notes/search?keyword=apple   200 OK
Sort by Date button      â†’ GET /notes/search?sort_by=date    200 OK
Lookup Iterative button  â†’ GET /notes/lookup?title=Apple+Harvest+Notes&algo=iterative  200 OK
Lookup Recursive button  â†’ GET /notes/lookup?title=Budget+Draft&algo=recursive         200 OK
work quick-jump button   â†’ GET /notes/quick-find?tag=work    200 OK
```

---

## Part 3 â€” Intelligence Layer Evidence

### Mock mode â€” no API key required

`MOCK_AI=1` in `.env` (default). The `_mock_response()` function extracts the first 3
significant words as tags and the first sentence (â‰¤20 words) as the summary.
No network call, no signup, no internet.

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

All 8 return valid JSON with `"tags"` (list) and `"summary"` (string).

### POST /notes with ai_suggestion

```
POST /notes
Body: {"title":"Payments API down","content":"Payments API returning 503 errors, escalated to infra team.","tag":"work","owner_id":1}

Response 201:
{
  "id": 47,
  "title": "Payments API down",
  "content": "Payments API returning 503 errors, escalated to infra team.",
  "tag": "work",
  "severity": null,
  "owner_id": 1,
  "created_at": "2026-08-04T16:48:40.218Z",
  "ai_suggestion": {
    "tags": ["payments", "api", "returning"],
    "summary": "Payments API returning 503 errors, escalated to infra team"
  }
}
```

### Non-fatal AI failure

If the AI response cannot be parsed, `ai_suggestion` is `null` and the note is still created:

```
POST /notes â†’ 201 Created
{
  "id": 48,
  "title": "Test note",
  "ai_suggestion": null
}

Backend stdout: [AI] parse failed for note 48: ... | raw='not json'
```

### Frontend AI Suggests panel

```
1. Add note: "Kafka consumer lag growing on orders topic, scaled up consumers to handle load."
2. POST /notes â†’ 201
   ai_suggestion: {"tags": ["kafka","consumer","lag"], "summary": "Kafka consumer lag growing..."}
3. New note card renders:
   - Blue "AI Suggests:" panel with tags "kafka, consumer, lag"
   - Summary: "Kafka consumer lag growing on orders topic, scaled up consumers to handle load"
   - Button: Apply "kafka" as tag
4. Click Apply â†’ PUT /notes/34  Body: {"tag":"kafka"}  â†’ 200
5. Tag chip list updates to include "kafka"
```

### Semantic search â€” two required rubric queries

```
GET /notes/smart-search?q=leg+day+exercise+plan
Response:
[
  {"id":29,"title":"Gym schedule change",  "similarity":0.6034,
   "content":"Switch leg day to Thursday and move the rest day to Sunday this week."},
  {"id":24,"title":"Morning workout plan", "similarity":0.5752,
   "content":"Do 30 minutes of cardio followed by strength training focused on legs and core."},
  {"id":31,"title":"Weekend hiking trip",  "similarity":0.3599,
   "content":"Plan a short hiking trip to a nearby trail..."}
]
â†’ "Gym schedule change" is #1 in top 3 âœ“

GET /notes/smart-search?q=dinner+ideas+with+vegetables
Response:
[
  {"id":28,"title":"Recipe idea",    "similarity":0.5132,
   "content":"Try making a vegetable stir fry with broccoli, bell peppers, and soy sauce tonight."},
  {"id":25,"title":"Grocery list",   "similarity":0.4191,
   "content":"Buy milk, eggs, spinach, chicken breast, and whole wheat bread for the week."},
  {"id":31,"title":"Weekend hiking trip","similarity":0.2071, ...}
]
â†’ "Recipe idea" is #1 in top 3 âœ“
```

### Smart Search vs keyword search distinction

```
Smart Search (AI):   GET /notes/smart-search?q=leg+day+exercise+plan
  â†’ Ranks by cosine similarity of text embeddings
  â†’ Returns "Gym schedule change" even though query shares NO exact keywords with content
  â†’ Uses: sentence-transformers/all-MiniLM-L6-v2 model, numpy cosine similarity

Keyword Search:      GET /notes/search?keyword=leg
  â†’ Ranks by literal count of "leg" in note content
  â†’ Only returns notes that contain the word "leg" verbatim
  â†’ Uses: insertion_sort_by_key() from algorithms.py
```

The two controls are visually distinct in the frontend:
- **Ranked Search** section (white background) â€” keyword input + Sort buttons
- **Smart Search (AI)** section (blue background, AI badge) â€” separate input + Search button

### Model download and offline operation

```bash
# First run â€” internet required (one time only)
py -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
# Downloads ~90MB to ~/.cache/huggingface/hub/

# All subsequent runs â€” fully offline, zero API key
uvicorn main:app --reload
# GET /notes/smart-search works with no internet and no LLM_API_KEY
```

Model: `sentence-transformers/all-MiniLM-L6-v2`
Cache location: `~/.cache/huggingface/hub/`
Pin in requirements.txt: `sentence-transformers==3.0.0`

---

## Git Workflow

Feature branches and pull requests per part:
- `feature/part1-backend` â†’ merged to `main` via PR
- `feature/part2-ranking` â†’ merged to `main` via PR
- `feature/part3-intelligence` â†’ merged to `main` via PR

Commits are incremental with meaningful messages. PRs are visible in the repository's
Pull Requests history.

---

## Secrets

- `.env` is **never committed** â€” it is listed in `.gitignore`
- `.env.example` ships with placeholder variable names only
- No API keys appear anywhere in the committed code

---

## Optional Real LLM Path (Groq)

If `MOCK_AI=0` and `LLM_API_KEY` is set, the app calls Groq's free API tier
(`llama3-8b-8192` model). To use it:

1. Sign up at https://console.groq.com (free, no payment)
2. Create an API key
3. Set in `.env`: `MOCK_AI=0` and `LLM_API_KEY=your_key`
4. Free tier: 30 req/min, 14,400 req/day

The graded baseline is `MOCK_AI=1` â€” no Groq account required.
