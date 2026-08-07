# Phase 4 — AI Service
# Fully implemented in Phase 4. This stub lets the project run in Phase 1/2/3.
import os
import re
import json
from dotenv import load_dotenv

load_dotenv()

MOCK_AI = os.getenv("MOCK_AI", "1") == "1"
API_KEY = os.getenv("LLM_API_KEY", "")

AUTOTAG_SYSTEM_PROMPT = """
## Instructions
You are an AI assistant that reads a short note and extracts structured metadata from it.
Your job is to return ONLY a JSON object — nothing else.

## Context
The notes are written by on-call support engineers at Zomato during or after incidents.
Tags are used to categorize notes for fast retrieval during live incidents.
Summaries are used as one-line subtitles in a note list view.

## Input
The user will provide the full text content of a single note.

## Constraints
- Return ONLY a valid JSON object. No markdown fences, no explanation, no text before or after the JSON.
- The JSON must have exactly two keys: "tags" and "summary".
- "tags" must be a list of 1 to 3 short lowercase keyword strings (single words preferred).
- "summary" must be a single sentence of at most 20 words.
- Do not include any text outside the JSON object — not even a newline before or after it.

## Output Format
{"tags": ["tag1", "tag2"], "summary": "One sentence summary of at most twenty words."}
"""


def _mock_response(user_message: str) -> str:
    stopwords = {"the", "a", "an", "is", "in", "on", "at", "to", "for",
                 "of", "and", "or", "with", "do", "my", "by", "it", "its"}
    words = [w.lower() for w in re.findall(r'\b[a-zA-Z]+\b', user_message)]
    tags = [w for w in words if w not in stopwords][:3]
    first_sentence = re.split(r'[.!?]', user_message)[0].strip()
    summary = " ".join(first_sentence.split()[:20])
    return json.dumps({"tags": tags, "summary": summary})


def get_ai_response(user_message: str, system_prompt: str) -> str:
    if MOCK_AI:
        return _mock_response(user_message)
    # Real path — only used when MOCK_AI=0 and LLM_API_KEY is set
    from groq import Groq
    client = Groq(api_key=API_KEY)
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
    )
    return response.choices[0].message.content
