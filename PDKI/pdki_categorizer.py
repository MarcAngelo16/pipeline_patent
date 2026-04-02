#!/usr/bin/env python3
"""
PDKI Categoriser — AI relevance assessment for PDKI results vs a source Google Patent.

Usage:
    from PDKI.pdki_categorizer import categorize_result

    result_info = categorize_result(patent_data, pdki_result, api_key)
    # → {"category": "relevant", "score": 82, "reasoning": "..."}
"""

import json
import anthropic

HAIKU_MODEL = "claude-haiku-4-5-20251001"

CATEGORIZER_SYSTEM = """You are a patent relevance assessor for the Indonesian patent registry (PDKI).
Determine whether a PDKI patent result is relevant to a given source Google Patent.

Assess based on:
1. Subject matter / technology overlap (abstract, description, claims)
2. Assignee match (same company or subsidiary)
3. Inventor match (same inventors)

Score 0-100:
- 70-100 → relevant   (strong overlap, likely same invention or patent family)
- 40-69  → uncertain  (partial overlap, needs human review)
- 0-39   → not_relevant (different technology or unrelated)

Respond ONLY with valid JSON, no explanation, no markdown."""

CATEGORIZER_USER_TMPL = """Source Patent (Google Patents):
Title: {title}
Abstract: {abstract}
Claims: {claims}
Inventors: {inventors}
Assignees: {assignees}

PDKI Result:
Title: {pdki_title}
Abstract: {pdki_abstract}
Inventors: {pdki_inventors}
Assignees: {pdki_assignees}

Respond with:
{{
  "score": 0-100,
  "category": "relevant|uncertain|not_relevant",
  "reasoning": "2-3 sentences max"
}}"""


def _names(items) -> str:
    """Join a list that may contain strings or dicts with a 'name' key."""
    if not items:
        return ""
    parts = []
    for item in items:
        if isinstance(item, dict):
            parts.append(item.get("name") or "")
        else:
            parts.append(str(item))
    return ", ".join(p for p in parts if p)


def _build_prompt(patent_data: dict, result: dict) -> str:
    """Format the user prompt for one PDKI result against a source patent."""
    detail = result.get("detail") or {}
    claims_raw = patent_data.get("claims") or []
    if isinstance(claims_raw, list):
        claims_text = " | ".join(str(c) for c in claims_raw[:2])
    else:
        claims_text = str(claims_raw)

    return CATEGORIZER_USER_TMPL.format(
        title         = (patent_data.get("title") or "")[:300],
        abstract      = (patent_data.get("abstract") or "")[:800],
        claims        = claims_text[:600],
        inventors     = _names(patent_data.get("inventors")),
        assignees     = _names(patent_data.get("assignees")),
        pdki_title    = (detail.get("title") or result.get("text") or "")[:300],
        pdki_abstract = (detail.get("abstract") or "")[:600],
        pdki_inventors= _names(detail.get("inventors")),
        pdki_assignees= _names(detail.get("assignees")),
    )


def categorize_result(patent_data: dict, result: dict, api_key: str) -> dict:
    """
    Call Haiku to assess relevance of one PDKI result against the source patent.

    Args:
        patent_data: Google Patent metadata (title, abstract, claims, inventors, assignees)
        result:      PDKI result dict with 'detail' sub-dict
        api_key:     Anthropic API key

    Returns:
        {
            "category":  "relevant" | "uncertain" | "not_relevant",
            "score":     int (0-100),
            "reasoning": str
        }
    """
    client = anthropic.Anthropic(api_key=api_key)
    prompt = _build_prompt(patent_data, result)

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=300,
        system=CATEGORIZER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    parsed   = json.loads(raw)
    category = parsed.get("category", "uncertain")
    if category not in ("relevant", "not_relevant", "uncertain"):
        category = "uncertain"

    return {
        "category":  category,
        "score":     int(parsed.get("score", 0)),
        "reasoning": str(parsed.get("reasoning", "")),
    }
