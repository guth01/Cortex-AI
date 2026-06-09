"""
Sufficiency Judge — evaluates whether retrieved notes can answer the user's question.

Uses a dedicated Gemini API key (GEMINI_KEYS[0]) to classify retrieved context into:
  - SUFFICIENT    : Notes can fully answer the question
  - PARTIAL       : Notes partially cover the topic; gaps exist
  - INSUFFICIENT  : Notes do not cover the topic meaningfully

The judge never generates the answer — it only evaluates retrieval quality.
This keeps the two Gemini keys cleanly separated:
  Key 0 (judge)  → this module
  Key 1 (answer) → synthesis_node in nodes.py
"""

import os
import re
import json
import itertools
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid verdicts
# ---------------------------------------------------------------------------

VALID_VERDICTS = {"SUFFICIENT", "PARTIAL", "INSUFFICIENT"}

# ---------------------------------------------------------------------------
# Judge prompt (exactly as specified in requirements)
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = """You are a retrieval evaluator.

Determine whether the question can be answered using ONLY the retrieved context.

Return ONLY valid JSON with no additional text outside the JSON object.

Schema:
{
  "verdict": "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT",
  "reason": "short explanation"
}

Definitions:

SUFFICIENT:
The retrieved context contains enough information to answer the question accurately and completely.

PARTIAL:
The retrieved context contains some relevant information but important details are missing.

INSUFFICIENT:
The retrieved context does not contain enough information to answer the question."""


# ---------------------------------------------------------------------------
# Dedicated judge LLM factory — always uses key index 0
# ---------------------------------------------------------------------------

_judge_key: str | None = None


def _build_judge_llm() -> ChatGoogleGenerativeAI:
    """
    Build a Gemini LLM instance using the FIRST key in GEMINI_API_KEYS.
    This key is reserved exclusively for the Sufficiency Judge.
    Falls back to GEMINI_API_KEY (single-key mode) if GEMINI_API_KEYS is absent.
    """
    global _judge_key

    if _judge_key is None:
        keys_str = os.getenv("GEMINI_API_KEYS", "")
        if keys_str:
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]
            _judge_key = keys[0]  # Always key index 0
        else:
            single = os.getenv("GEMINI_API_KEY", "")
            if not single:
                raise RuntimeError(
                    "GEMINI_API_KEY or GEMINI_API_KEYS must be set for the Sufficiency Judge"
                )
            _judge_key = single

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=_judge_key,
        temperature=0.0,  # Deterministic — classification task
    )


# ---------------------------------------------------------------------------
# JSON extraction helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> dict:
    """
    Parse judge response as JSON.

    Handles three common LLM output patterns:
    1. Clean JSON  → {"verdict": ..., "reason": ...}
    2. Markdown-fenced JSON  → ```json\n{...}\n```
    3. JSON embedded in surrounding prose

    Returns a dict with 'verdict' and 'reason' keys.
    Raises ValueError if no valid JSON can be extracted.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()

    # Try direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt to pull out first {...} block via regex
    match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from judge response: {raw[:300]}")


def _validate_verdict(data: dict) -> dict:
    """
    Validate and normalise the parsed judge dict.
    - Uppercases the verdict string
    - Defaults to PARTIAL if verdict is unrecognised (safe fallback)
    """
    verdict = str(data.get("verdict", "")).strip().upper()
    reason = str(data.get("reason", "No reason provided.")).strip()

    if verdict not in VALID_VERDICTS:
        print(
            f"[JUDGE] Unrecognised verdict '{verdict}', defaulting to PARTIAL"
        )
        verdict = "PARTIAL"

    return {"verdict": verdict, "reason": reason}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_sufficiency_judge(question: str, retrieved_context: str) -> dict:
    """
    Evaluate whether the retrieved notes are sufficient to answer the question.

    Args:
        question:          The user's original question.
        retrieved_context: Formatted string of all retrieved chunks.

    Returns:
        {
            "verdict": "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT",
            "reason":  str
        }

    On any failure (API error, malformed JSON), returns a safe PARTIAL verdict
    so the user always gets to choose a fallback rather than receiving a silent
    broken response.
    """
    print(f"[JUDGE] question='{question[:120]}'")
    print(f"[JUDGE] context_chars={len(retrieved_context)}")

    user_prompt = f"""Question:
{question}

Retrieved Context:
{retrieved_context}"""

    try:
        llm = _build_judge_llm()
        response = await llm.ainvoke([
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ])

        raw = response.content if hasattr(response, "content") else str(response)
        print(f"[JUDGE] raw_response='{raw[:300]}'")

        data = _extract_json(raw)
        result = _validate_verdict(data)

    except Exception as exc:
        # Never crash the pipeline — return a safe default
        print(f"[JUDGE] ERROR: {exc}. Defaulting to PARTIAL verdict.")
        result = {
            "verdict": "PARTIAL",
            "reason": f"Judge evaluation failed ({type(exc).__name__}); defaulting to PARTIAL for safety.",
        }

    print(f"[JUDGE] verdict={result['verdict']}")
    print(f"[JUDGE] reason={result['reason']}")
    return result
