"""
Agent tools — the actual capabilities the agent uses.

Tools are plain functions called by LangGraph nodes.
They are NOT LangChain tool objects — just clean Python functions.
"""

import os
import requests
from typing import Optional
import re

from db.chroma import get_session_collection
from utils.embedder import get_embeddings


# ============================================================================
# TOOL: search_notes
# ============================================================================

def search_notes(query: str, session_id: str, top_k: int = 5) -> dict:
    """
    Semantic search over the session's ChromaDB collection.

    Args:
        query:      Natural language query
        session_id: Active session ID (maps to ChromaDB collection)
        top_k:      Number of results to return (default 5)

    Returns:
        {
            "chunks": [{"content": str, "metadata": dict, "score": float}],
            "confidence": float,   # avg score of top-3 results
            "found": bool
        }
    """
    try:
        vs = get_session_collection(session_id)

        # similarity_search_with_relevance_scores returns (Document, score) pairs
        results = vs.similarity_search_with_relevance_scores(query, k=top_k)

        if not results:
            return {"chunks": [], "confidence": 0.0, "found": False}

        chunks = []
        for doc, score in results:
            chunks.append({
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": round(float(score), 4),
            })

        # Confidence = average score of top-3 results (or fewer if not enough)
        top3_scores = [c["score"] for c in chunks[:3]]
        confidence = sum(top3_scores) / len(top3_scores) if top3_scores else 0.0

        print(f"[TOOL:search_notes] query='{query}' -> {len(chunks)} chunks, confidence={confidence:.3f}")
        return {
            "chunks": chunks,
            "confidence": round(confidence, 4),
            "found": len(chunks) > 0,
        }

    except ValueError as e:
        # ChromaDB collection doesn't exist (session ended / invalid)
        print(f"[TOOL:search_notes] ChromaDB error: {e}")
        return {"chunks": [], "confidence": 0.0, "found": False, "error": str(e)}

    except Exception as e:
        print(f"[TOOL:search_notes] Unexpected error: {e}")
        return {"chunks": [], "confidence": 0.0, "found": False, "error": str(e)}


# ============================================================================
# TOOL: fetch_wikipedia_summary
# ============================================================================

def fetch_wikipedia_summary(topic: str) -> dict:
    """
    Fetch a clean summary from Wikipedia's REST API.

    Args:
        topic: Topic to look up (e.g. "Virtual memory", "Photosynthesis")

    Returns:
        {
            "title": str,
            "summary": str,   # 3-4 paragraph clean text
            "url": str,
            "found": bool
        }
    """
    try:
        # Wikipedia REST API — no key needed, returns clean extract
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{requests.utils.quote(topic)}"
        headers = {"User-Agent": "StudyAgentBot/1.0 (educational-ai-project)"}

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 404:
            print(f"[TOOL:wikipedia] Not found: '{topic}'")
            return {"title": topic, "summary": "", "url": "", "found": False}

        response.raise_for_status()
        data = response.json()

        # Extract and clean the text
        raw_text = data.get("extract", "")

        # Split into sentences and limit to ~4 paragraphs worth
        # Wikipedia extracts are already clean text, just truncate reasonably
        sentences = raw_text.split(". ")
        # Take up to ~20 sentences (roughly 3-4 paragraphs)
        summary_sentences = sentences[:20]
        summary = ". ".join(summary_sentences)
        if not summary.endswith("."):
            summary += "."

        # Clean up extra whitespace
        summary = re.sub(r"\s+", " ", summary).strip()

        title = data.get("title", topic)
        wiki_url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

        print(f"[TOOL:wikipedia] Fetched: '{title}' ({len(summary)} chars)")
        return {
            "title": title,
            "summary": summary,
            "url": wiki_url,
            "found": True,
        }

    except requests.RequestException as e:
        print(f"[TOOL:wikipedia] Request failed: {e}")
        return {"title": topic, "summary": "", "url": "", "found": False, "error": str(e)}

    except Exception as e:
        print(f"[TOOL:wikipedia] Unexpected error: {e}")
        return {"title": topic, "summary": "", "url": "", "found": False, "error": str(e)}


# ============================================================================
# TOOL: summarize_topic  (calls search_notes + Gemini)
# ============================================================================

DEPTH_PROMPTS = {
    "quick": "Give a brief 2-3 sentence overview suitable for a quick refresher.",
    "detailed": "Give a thorough explanation covering the main concepts, mechanisms, and examples.",
    "exam_revision": "Structure your response for exam revision: key definitions, important points, common exam questions, and memory tips.",
    "beginner": "Explain this as if to someone with no background. Use simple language, analogies, and avoid jargon.",
    "advanced": "Provide a deep, technical explanation assuming graduate-level background. Include edge cases, nuances, and connections to related concepts.",
}


def summarize_topic(
    topic: str,
    session_id: str,
    depth_level: str = "detailed",
    llm=None,
) -> dict:
    """
    Summarize a topic using the session's notes via RAG.

    Args:
        topic:       Topic to summarize
        session_id:  Active session ID for RAG
        depth_level: quick | detailed | exam_revision | beginner | advanced
        llm:         Gemini LLM instance (passed in from nodes)

    Returns:
        {
            "topic": str,
            "summary": str,
            "depth_level": str,
            "source_chunks_used": int
        }
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    if llm is None:
        raise ValueError("summarize_topic requires an LLM instance")

    # Step 1: Retrieve notes
    notes_result = search_notes(topic, session_id, top_k=6)
    chunks = notes_result.get("chunks", [])

    # Build context from notes
    if chunks:
        notes_context = "\n\n---\n\n".join([c["content"] for c in chunks])
        source_info = f"(from {len(chunks)} chunks in your notes)"
    else:
        notes_context = "No relevant notes found for this topic."
        source_info = "(no notes found — using general knowledge)"

    depth_instruction = DEPTH_PROMPTS.get(depth_level, DEPTH_PROMPTS["detailed"])

    system_prompt = f"""You are a focused study assistant. Your task is to summarize a topic based on the student's own notes.

{depth_instruction}

Use ONLY the provided notes as your primary source. If notes are insufficient, supplement with your knowledge but clearly indicate this."""

    user_prompt = f"""Topic: {topic}

Student's Notes:
{notes_context}

Please provide a {depth_level} summary of "{topic}" {source_info}."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    summary_text = response.content if hasattr(response, "content") else str(response)

    print(f"[TOOL:summarize_topic] topic='{topic}', depth={depth_level}, chunks={len(chunks)}")
    return {
        "topic": topic,
        "summary": summary_text,
        "depth_level": depth_level,
        "source_chunks_used": len(chunks),
    }


# ============================================================================
# TOOL: knowledge_gap_analysis
# ============================================================================

# Default expected topics per subject type (user can extend via Atlas later)
DEFAULT_TOPICS = {
    "math": ["algebra", "calculus", "statistics", "probability", "linear algebra", "differential equations"],
    "physics": ["mechanics", "thermodynamics", "electromagnetism", "optics", "quantum mechanics", "relativity"],
    "chemistry": ["atomic structure", "chemical bonding", "thermochemistry", "kinetics", "electrochemistry", "organic chemistry"],
    "biology": ["cell biology", "genetics", "evolution", "ecology", "physiology", "biochemistry"],
    "computer science": ["algorithms", "data structures", "operating systems", "networking", "databases", "software engineering"],
    "history": ["ancient history", "medieval history", "modern history", "world wars", "colonialism", "political revolutions"],
    "default": ["introduction", "key concepts", "principles", "applications", "examples", "practice problems"],
}

# Thresholds
WELL_COVERED_THRESHOLD = 0.55    # confidence >= this → well covered
SHALLOW_THRESHOLD = 0.30         # confidence between shallow and well_covered → shallow


def knowledge_gap_analysis(
    session_id: str,
    subject_name: str = "default",
    custom_topics: Optional[list] = None,
) -> dict:
    """
    Analyze which topics are well-covered, shallow, or missing in the session's notes.

    Args:
        session_id:    Active session ID for RAG
        subject_name:  Subject name to pick default topics (e.g. "computer science")
        custom_topics: Override with a specific list of topics to check

    Returns:
        {
            "well_covered": [str],
            "shallow": [str],
            "missing": [str],
            "details": {topic: {"confidence": float, "chunk_count": int}}
        }
    """
    # Determine topic list
    if custom_topics:
        topics = custom_topics
    else:
        # Fuzzy match subject name to our defaults
        subject_lower = subject_name.lower()
        matched_key = "default"
        for key in DEFAULT_TOPICS:
            if key in subject_lower or subject_lower in key:
                matched_key = key
                break
        topics = DEFAULT_TOPICS[matched_key]

    well_covered = []
    shallow = []
    missing = []
    details = {}

    print(f"[TOOL:gap_analysis] Analyzing {len(topics)} topics for session {session_id}")

    for topic in topics:
        result = search_notes(topic, session_id, top_k=5)
        confidence = result.get("confidence", 0.0)
        chunk_count = len(result.get("chunks", []))

        details[topic] = {"confidence": confidence, "chunk_count": chunk_count}

        if confidence >= WELL_COVERED_THRESHOLD:
            well_covered.append(topic)
        elif confidence >= SHALLOW_THRESHOLD:
            shallow.append(topic)
        else:
            missing.append(topic)

    print(f"[TOOL:gap_analysis] DONE covered={len(well_covered)}, shallow={len(shallow)}, missing={len(missing)}")
    return {
        "well_covered": well_covered,
        "shallow": shallow,
        "missing": missing,
        "details": details,
    }
