#!/usr/bin/env python3
"""
PDKI Pipeline - Full Phase 1 Orchestrator

Flow:
  1. Fetch Google Patent metadata (title, abstract, inventors, assignees)
  2. AI Planner (Haiku) → generates search_plan with normalized search terms
  3. Build PDKI batch list from search_plan + config caps
  4. Run Round 1 PDKI searches → collect results per batch
  5. Reflect: flag entities that returned 0 results
  6. AI Reflection (Haiku) → alternative terms for flagged entities
  7. Run Round 2 PDKI searches for flagged entities only
  8. Merge all rounds → deduplicate by URL → tag each with found_by[]
  9. Fetch detail page for each unique result
 10. Save output/{patent_id}_{timestamp}.json
"""

import gc
import os
import sys
import json
import time
import argparse
from datetime import datetime
from pathlib import Path

import anthropic

# ── Paths ────────────────────────────────────────────────────────────────────
PDKI_DIR      = Path(__file__).parent
PIPELINE_DIR  = PDKI_DIR.parent

# ── Load .env if present ─────────────────────────────────────────────────────
_env_file = PDKI_DIR / ".env"
if _env_file.exists():
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _v = _v.strip().strip('"').strip("'")
                os.environ.setdefault(_k.strip(), _v)
OUTPUT_DIR    = PIPELINE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Add parent dirs to path so we can import existing modules
sys.path.insert(0, str(PIPELINE_DIR))
sys.path.insert(0, str(PDKI_DIR))

from googlepatent_extract.google_patents_clean_extractor import (
    setup_chrome_driver,
    extract_patent_data,
)
from PDKI.PDKI_advanced import (
    setup_driver as setup_pdki_driver,
    wait_for_page,
    set_category_paten,
    fill_advanced_search,
    click_terapkan,
    set_pagination_100,
    extract_links,
)
from PDKI.PDKI_detail_extractor import (
    setup_driver as setup_detail_driver,
    extract_detail,
)

# ── Search config ─────────────────────────────────────────────────────────────
PDKI_SEARCH_CONFIG = {
    "max_title_keywords":    3,
    "max_assignee_searches": 2,
    "max_inventor_searches": 3,
    "search_timeout_sec":    30,
    "inter_search_delay_sec": 3,
}

HAIKU_MODEL = "claude-haiku-4-5-20251001"


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: Google Patent extraction
# ─────────────────────────────────────────────────────────────────────────────

def fetch_google_patent(patent_id: str) -> dict:
    """Fetch metadata from Google Patents for the given patent ID."""
    url = f"https://patents.google.com/patent/{patent_id}"
    print(f"\n[Step 1] Fetching Google Patent: {url}")

    driver = setup_chrome_driver()
    try:
        data = extract_patent_data(driver, url)
    finally:
        driver.quit()

    if data.get("error"):
        raise RuntimeError(f"Google Patents extraction failed: {data['error']}")

    print(f"   Title:     {data.get('title', '')[:80]}")
    print(f"   Inventors: {len(data.get('inventors', []))}")
    print(f"   Assignees: {len(data.get('assignees', []))}")
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Step 2: AI Search Planner
# ─────────────────────────────────────────────────────────────────────────────

PLANNER_SYSTEM = """You are a patent search specialist for the Indonesian patent registry (PDKI).
Your job is to generate optimized search terms from a Google Patent metadata.

Rules:
- title_keywords: extract single-word core technical terms from the title and abstract.
  Each keyword must be ONE word only — no phrases, no multi-word terms.
  Prefer the root compound name or active ingredient (e.g. "valbenazine" not "valbenazine salts").
  Avoid generic words like "method", "composition", "use", "system", "process", "salt", "polymorph".
- assignees: strip legal suffixes (Inc, Corp, Ltd, BV, SRL, GmbH, SA, NV, LLC, Co., plc, AG)
  and division descriptors. Keep the core brand/company name that PDKI is most likely to store.
- inventors: normalize to "LastName FirstInitial" format (e.g. "Bernard J. Scallon" → "Scallon B").
  For hyphenated surnames keep the full surname. For multi-word surnames use the last word only if ambiguous.

Respond ONLY with a valid JSON object, no explanation, no markdown.
"""

PLANNER_USER_TMPL = """Patent metadata:
Title: {title}
Abstract: {abstract}
Inventors: {inventors}
Assignees: {assignees}

Generate a search plan with this exact structure:
{{
  "title_keywords": ["keyword1", "keyword2", "keyword3"],
  "assignees": [
    {{
      "original": "Full Legal Name",
      "search_term": "Stripped Name",
      "reasoning": "why stripped this way"
    }}
  ],
  "inventors": [
    {{
      "original": "Full Name",
      "search_term": "LastName F"
    }}
  ]
}}

Limit: up to {max_kw} title keywords, up to {max_assignee} assignees, up to {max_inventor} inventors.
"""


def ai_plan_searches(patent_data: dict, api_key: str) -> dict:
    """Call Haiku to generate the search plan from patent metadata."""
    print("\n[Step 2] AI search planning...")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = PLANNER_USER_TMPL.format(
        title=patent_data.get("title", ""),
        abstract=(patent_data.get("abstract") or "")[:1000],
        inventors=", ".join(patent_data.get("inventors", [])),
        assignees=", ".join(patent_data.get("assignees", [])),
        max_kw=PDKI_SEARCH_CONFIG["max_title_keywords"],
        max_assignee=PDKI_SEARCH_CONFIG["max_assignee_searches"],
        max_inventor=PDKI_SEARCH_CONFIG["max_inventor_searches"],
    )

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        system=PLANNER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    plan = json.loads(raw)

    print(f"   Title keywords: {plan.get('title_keywords', [])}")
    print(f"   Assignees:      {[a['search_term'] for a in plan.get('assignees', [])]}")
    print(f"   Inventors:      {[i['search_term'] for i in plan.get('inventors', [])]}")

    return plan


# ─────────────────────────────────────────────────────────────────────────────
# Step 3: Build PDKI batch list
# ─────────────────────────────────────────────────────────────────────────────

def build_batches(plan: dict) -> list[dict]:
    """
    Convert the AI search plan into a flat list of single-field PDKI batches.
    Each batch has: judul, nama_inventor, nama_pemegang, _tag (internal label).
    """
    batches = []

    for kw in plan.get("title_keywords", []):
        batches.append({
            "judul": kw,
            "nama_inventor": None,
            "nama_pemegang": None,
            "_tag": f"title:{kw}",
        })

    for a in plan.get("assignees", []):
        batches.append({
            "judul": None,
            "nama_inventor": None,
            "nama_pemegang": a["search_term"],
            "_tag": f"assignee:{a['search_term']}",
        })

    for inv in plan.get("inventors", []):
        batches.append({
            "judul": None,
            "nama_inventor": inv["search_term"],
            "nama_pemegang": None,
            "_tag": f"inventor:{inv['search_term']}",
        })

    return batches


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 & 7: Run PDKI batches (shared for Round 1 and Round 2)
# ─────────────────────────────────────────────────────────────────────────────

def run_pdki_batches(batches: list[dict], driver, round_label: str = "R1") -> list[dict]:
    """
    Execute a list of PDKI batches using an already-loaded driver.
    Returns a list of: {tag, batch, links[], hit_count}
    Driver must already be on the PDKI search page with category set to Paten.
    """
    results = []

    for i, batch in enumerate(batches, 1):
        tag = batch["_tag"]
        search_fields = {k: v for k, v in batch.items() if not k.startswith("_")}

        print(f"\n  [{round_label}] Batch {i}/{len(batches)}: {tag}")

        fill_advanced_search(driver, **search_fields)

        label = tag.replace(":", "_").replace(" ", "-")
        if not click_terapkan(driver, label=label, screenshot=False):
            print(f"    Terapkan failed — skipping")
            results.append({"tag": tag, "batch": search_fields, "links": [], "hit_count": 0})
            continue

        links = extract_links(driver)
        print(f"    {len(links)} links found")

        results.append({
            "tag": tag,
            "batch": search_fields,
            "links": links,
            "hit_count": len(links),
        })

        if i < len(batches):
            time.sleep(PDKI_SEARCH_CONFIG["inter_search_delay_sec"])

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 & 6: Reflection — AI generates alternative terms for zero-hit entities
# ─────────────────────────────────────────────────────────────────────────────

REFLECTION_SYSTEM = """You are a patent search specialist for the Indonesian patent registry (PDKI).
Some searches returned zero results. Suggest ONE alternative search term per entity.

Guidelines:
- For assignees: try a shorter form (remove subsidiary/division name, keep only the root brand).
  If already short, try the Indonesian variation if known.
- For inventors: try full first name instead of initial, or swap to "FirstName LastName" order.
- For title keywords: translate the technical term to Bahasa Indonesia using your knowledge.
  PDKI stores Indonesian-language titles, so translation is high-value.

Respond ONLY with valid JSON, no explanation, no markdown.
"""

REFLECTION_USER_TMPL = """These searches returned 0 results on PDKI:
{zero_results}

Patent context:
Title: {title}
Assignees (original): {assignees}
Inventors (original): {inventors}

For each zero-result entity, suggest ONE alternative search term.
Respond with this structure:
{{
  "alternatives": [
    {{
      "original_tag": "assignee:UCB Biopharma",
      "alternative_term": "UCB",
      "field": "nama_pemegang",
      "reasoning": "strip division descriptor"
    }},
    {{
      "original_tag": "title:monoclonal antibody",
      "alternative_term": "antibodi monoklonal",
      "field": "judul",
      "reasoning": "Indonesian translation"
    }}
  ]
}}
"""


def ai_reflect_zero_results(
    zero_result_batches: list[dict],
    patent_data: dict,
    api_key: str,
) -> list[dict]:
    """
    Call Haiku with zero-result entities → returns alternative batch list.
    Returns a list of new batches to run (same structure as build_batches output).
    """
    print(f"\n[Step 6] AI reflection for {len(zero_result_batches)} zero-result entities...")

    client = anthropic.Anthropic(api_key=api_key)

    zero_summary = "\n".join(
        f"  - {b['tag']} (field: {'judul' if b['batch'].get('judul') else 'nama_inventor' if b['batch'].get('nama_inventor') else 'nama_pemegang'})"
        for b in zero_result_batches
    )

    prompt = REFLECTION_USER_TMPL.format(
        zero_results=zero_summary,
        title=patent_data.get("title", ""),
        assignees=", ".join(patent_data.get("assignees", [])),
        inventors=", ".join(patent_data.get("inventors", [])),
    )

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=1024,
        system=REFLECTION_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    reflection = json.loads(raw)
    alternatives = reflection.get("alternatives", [])

    new_batches = []
    for alt in alternatives:
        field    = alt.get("field", "judul")
        term     = alt.get("alternative_term", "")
        orig_tag = alt.get("original_tag", "")

        if not term:
            continue

        batch = {
            "judul":          term if field == "judul"          else None,
            "nama_inventor":  term if field == "nama_inventor"  else None,
            "nama_pemegang":  term if field == "nama_pemegang"  else None,
            "_tag":           f"{orig_tag}→alt:{term}",
        }
        new_batches.append(batch)
        print(f"   Alternative: {orig_tag} → {term!r}  ({alt.get('reasoning', '')})")

    return new_batches


# ─────────────────────────────────────────────────────────────────────────────
# Step 8: Merge + deduplicate all results
# ─────────────────────────────────────────────────────────────────────────────

def merge_results(all_batch_results: list[dict]) -> list[dict]:
    """
    Merge results from all batches (Round 1 + Round 2).
    Deduplicates by URL.
    Each unique result gets a found_by[] list of tags that found it.
    """
    seen: dict[str, dict] = {}  # url → merged entry

    for batch_result in all_batch_results:
        tag   = batch_result["tag"]
        links = batch_result["links"]

        for link in links:
            url = link["url"]
            if url in seen:
                if tag not in seen[url]["found_by"]:
                    seen[url]["found_by"].append(tag)
            else:
                seen[url] = {
                    "url":      url,
                    "text":     link.get("text", ""),
                    "found_by": [tag],
                    "detail":   None,
                }

    merged = list(seen.values())
    print(f"\n[Step 8] Merged: {sum(r['hit_count'] for r in all_batch_results)} raw hits → {len(merged)} unique results")
    return merged


# ─────────────────────────────────────────────────────────────────────────────
# Step 9: Fetch PDKI detail pages
# ─────────────────────────────────────────────────────────────────────────────

def fetch_details(unique_results: list[dict]) -> list[dict]:
    """Visit each unique PDKI URL and extract the detail page."""
    print(f"\n[Step 9] Fetching details for {len(unique_results)} unique results...")

    driver = setup_detail_driver()
    try:
        for i, result in enumerate(unique_results, 1):
            print(f"\n  [{i}/{len(unique_results)}] {result.get('text', '')[:60]}")
            detail = extract_detail(driver, result["url"], debug=False)
            if detail:
                result["detail"] = detail
                print(f"    Title:    {detail.get('title')}")
                print(f"    Status:   {detail.get('status')}")
            else:
                print(f"    Failed to extract detail")

            if i < len(unique_results):
                time.sleep(2)
    finally:
        driver.quit()

    fetched = sum(1 for r in unique_results if r["detail"])
    print(f"\n   Details fetched: {fetched}/{len(unique_results)}")
    return unique_results


# ─────────────────────────────────────────────────────────────────────────────
# Step 10: Save output
# ─────────────────────────────────────────────────────────────────────────────

def save_output(patent_id: str, patent_data: dict, search_plan: dict,
                all_batch_results: list[dict], unique_results: list[dict]) -> str:

    ts = int(time.time())
    filename = OUTPUT_DIR / f"{patent_id}_{ts}.json"

    # Tally per-tag stats
    search_stats = [
        {"tag": r["tag"], "hits": r["hit_count"]}
        for r in all_batch_results
    ]

    output = {
        "generated":      str(datetime.now()),
        "google_patent_id": patent_id,
        "source_patent":  patent_data,
        "search_plan":    search_plan,
        "search_stats":   search_stats,
        "stats": {
            "searches_run":    len(all_batch_results),
            "raw_hits":        sum(r["hit_count"] for r in all_batch_results),
            "unique_results":  len(unique_results),
            "details_fetched": sum(1 for r in unique_results if r["detail"]),
        },
        "pdki_results": unique_results,
    }

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"\n[Step 10] Saved: {filename}")
    return str(filename)


# ─────────────────────────────────────────────────────────────────────────────
# Main orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(patent_id: str, api_key: str) -> str:
    print("=" * 60)
    print(f"PDKI Pipeline — {patent_id}")
    print("=" * 60)

    # ── Step 1: Google Patent ──────────────────────────────────────────────
    patent_data = fetch_google_patent(patent_id)

    gc.collect()
    time.sleep(3)  # let OS reclaim Chrome memory before next driver

    # ── Step 2: AI search plan ─────────────────────────────────────────────
    search_plan = ai_plan_searches(patent_data, api_key)

    # ── Step 3: Build batches ──────────────────────────────────────────────
    batches_r1 = build_batches(search_plan)
    print(f"\n[Step 3] Built {len(batches_r1)} Round 1 batches")

    # ── Steps 4: Run Round 1 ───────────────────────────────────────────────
    print(f"\n[Step 4] Running Round 1 searches...")
    pdki_driver = setup_pdki_driver()
    all_batch_results = []

    try:
        pdki_driver.get("https://pdki-indonesia.dgip.go.id/search")
        if not wait_for_page(pdki_driver):
            raise RuntimeError("PDKI page failed to load")
        if not set_category_paten(pdki_driver):
            raise RuntimeError("Could not set category to Paten")
        set_pagination_100(pdki_driver)

        r1_results = run_pdki_batches(batches_r1, pdki_driver, round_label="R1")
        all_batch_results.extend(r1_results)

        # ── Step 5: Find zero-result entities ─────────────────────────────
        zero_result_batches = [r for r in r1_results if r["hit_count"] == 0]
        print(f"\n[Step 5] Zero-result entities: {len(zero_result_batches)}/{len(r1_results)}")

        # ── Step 6 & 7: Reflection + Round 2 ──────────────────────────────
        if zero_result_batches:
            batches_r2 = ai_reflect_zero_results(zero_result_batches, patent_data, api_key)

            if batches_r2:
                print(f"\n[Step 7] Running Round 2 searches ({len(batches_r2)} batches)...")
                r2_results = run_pdki_batches(batches_r2, pdki_driver, round_label="R2")
                all_batch_results.extend(r2_results)
            else:
                print("   No alternatives generated — skipping Round 2")
        else:
            print("   All searches returned results — no Round 2 needed")

    finally:
        pdki_driver.quit()
        gc.collect()
        time.sleep(3)  # let OS reclaim Chrome memory before detail driver

    # ── Step 8: Merge + deduplicate ────────────────────────────────────────
    unique_results = merge_results(all_batch_results)

    # ── Step 9: Fetch details ──────────────────────────────────────────────
    if unique_results:
        unique_results = fetch_details(unique_results)
    else:
        print("\n[Step 9] No results to fetch details for")

    # ── Step 10: Save ──────────────────────────────────────────────────────
    output_file = save_output(patent_id, patent_data, search_plan, all_batch_results, unique_results)

    print("\n" + "=" * 60)
    print("Pipeline complete")
    print(f"  Searches run:    {len(all_batch_results)}")
    print(f"  Unique results:  {len(unique_results)}")
    print(f"  Details fetched: {sum(1 for r in unique_results if r['detail'])}")
    print(f"  Output:          {output_file}")
    print("=" * 60)

    return output_file


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PDKI Full Pipeline")
    parser.add_argument("patent_id", help="Google Patent ID (e.g. US6656718B2)")
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ANTHROPIC_API_KEY"),
        help="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )
    args = parser.parse_args()

    if not args.api_key:
        print("Error: ANTHROPIC_API_KEY not set. Pass --api-key or export the env var.")
        sys.exit(1)

    run_pipeline(args.patent_id, args.api_key)


if __name__ == "__main__":
    main()
