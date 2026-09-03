"""
Wide-net keyword search over your generated markdown files.

Searches the FULL text of every file — frontmatter company/position AND the
generated Context/Conversation summary/Notes/manual-notes text — not just
structured fields. Real signal (a business name mentioned only in a written
summary, or in someone else's file) often isn't in company/position at all.

Expands each query concept via a small hand-curated synonym/variant map
(spacing/hyphenation variants, common near-synonyms) rather than requiring
the literal query words to appear verbatim. Never a hard pass/fail filter:
results are ranked candidates for you to review, each shown with its
evidence fields and the matched snippet — you judge fit, not the script.
Explicit "no strong match" when nothing hits, rather than guessing.

The ceiling — what this can't do no matter how wide the synonym map gets:
  1. Two genuinely unrelated words for the same real role/company, with no
     shared vocabulary and no synonym pair anyone thought to add in advance
     ("growth hacker" vs. "demand generation lead").
  2. Recognising a company name as relevant from world knowledge the file's
     own text doesn't contain (a stylised or invented-sounding company name
     with zero descriptive words anywhere near it).
  3. Compositional/relational questions that need reasoning about a company
     as an entity ("who works at a company that recently raised a round"),
     not matching a word in a field.
  4. Cross-file evidence — a fact about person X that's only written down in
     person Y's file. This tool searches each file's own text; it has no way
     to connect a fact that lives in someone else's record.
Only a full read by an LLM solves 1-3, and only if the answer is present
somewhere in your own text or the model's background knowledge. Nothing
solves a fact nobody ever wrote down anywhere.

Usage:
    python3 query.py "who runs a digital marketing agency"
    python3 query.py "who does Google Ads" --limit 20
"""
import argparse
import glob
import os
import re

import yaml

import config

VAULT = config.VAULT_DIR
NETWORK_DIR = os.path.join(VAULT, config.NETWORK_SUBFOLDER)
MARKER = "<!-- MANUAL NOTES BELOW -->"

STOPWORDS = {
    "a", "an", "the", "who", "what", "which", "does", "do", "did", "is",
    "are", "was", "were", "in", "on", "at", "of", "for", "to", "and", "or",
    "with", "runs", "run", "running", "works", "work", "working", "someone",
    "any", "anyone", "me", "my", "i", "know", "person", "people",
}

# Canonical concept -> extra literal substrings to also search for. This is
# a starting list — extend it as you find "should have matched" gaps (see
# the toolkit's build-log notes on this pattern for the process).
CONCEPT_SYNONYMS = {
    "agency": ["agency", "agencies", "studio", "consultancy", "collective"],
    "digital": ["digital"],
    "marketing": ["marketing", "marketer", "growth", "demand gen", "demand generation", "brand"],
    "trademark": ["trademark", "trade mark", "trade-mark", "ip ", "intellectual property"],
    "seo": ["seo", "search engine optimization", "search engine optimisation", "organic search"],
    "ads": ["ads", "advertising", "ppc", "paid media", "paid social", "media buying"],
    "google": ["google"],
    "ecommerce": ["ecommerce", "e-commerce", "e commerce", "shopify"],
    "consultant": ["consultant", "consulting", "freelance", "freelancer"],
    "founder": ["founder", "co-founder", "cofounder", "owner"],
    "lawyer": ["lawyer", "solicitor", "attorney", "legal counsel"],
}


def normalize(word):
    return word.lower().strip(".,!?;:'\"()[]")


def expand_concept(word):
    w = normalize(word)
    if not w:
        return []
    variants = {w}
    if w.endswith("s") and len(w) > 3:
        variants.add(w[:-1])
    if w in CONCEPT_SYNONYMS:
        variants.update(CONCEPT_SYNONYMS[w])
    if w.endswith("s") and w[:-1] in CONCEPT_SYNONYMS:
        variants.update(CONCEPT_SYNONYMS[w[:-1]])
    return list(variants)


def query_concepts(query):
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-']*", query)
    concepts = []
    for t in tokens:
        w = normalize(t)
        if w in STOPWORDS or not w:
            continue
        concepts.append(w)
    return concepts


def load_people():
    people = []
    for path in sorted(glob.glob(os.path.join(NETWORK_DIR, "*.md"))):
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if "---" not in content:
            continue
        parts = content.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            fm = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            continue
        body = parts[2]
        haystack = " ".join([
            str(fm.get("company") or ""),
            str(fm.get("position") or ""),
            body,
        ]).lower()
        people.append({
            "file": os.path.basename(path),
            "name": fm.get("name") or os.path.basename(path)[:-3],
            "company": fm.get("company") or "",
            "position": fm.get("position") or "",
            "sources": fm.get("sources") or [],
            "met_in_person": fm.get("met_in_person"),
            "has_vault_note": fm.get("has_vault_note"),
            "message_count": fm.get("message_count"),
            "tier_override": fm.get("tier_override") or "",
            "haystack": haystack,
        })
    return people


def find_snippet(haystack, term, width=60):
    idx = haystack.find(term)
    if idx == -1:
        return ""
    start = max(0, idx - width // 2)
    end = min(len(haystack), idx + len(term) + width // 2)
    return re.sub(r"\s+", " ", haystack[start:end].strip())


def search(query, limit=30):
    concepts = query_concepts(query)
    if not concepts:
        print("Couldn't extract any searchable terms from that query.")
        return

    people = load_people()
    results = []
    for p in people:
        matched_concepts = []
        matched_snippets = []
        for concept in concepts:
            hit_variant = None
            for v in expand_concept(concept):
                if v in p["haystack"]:
                    hit_variant = v
                    break
            if hit_variant:
                matched_concepts.append(concept)
                matched_snippets.append((concept, hit_variant, find_snippet(p["haystack"], hit_variant)))
        if matched_concepts:
            results.append((len(matched_concepts), matched_concepts, matched_snippets, p))

    if not results:
        print(f'No strong keyword match found for: "{query}"')
        print("This may mean nobody in your network fits — or it may be a phrasing")
        print("this search doesn't catch. See the ceiling notes in this file's")
        print("docstring, and consider a full LLM read for anything important enough")
        print("that you don't trust a negative result on.")
        return

    results.sort(key=lambda r: r[0], reverse=True)
    n_concepts = len(concepts)
    full_matches = [r for r in results if r[0] == n_concepts]
    partial_matches = [r for r in results if r[0] < n_concepts]

    print(f'{len(results)} candidate(s) for: "{query}"  (matched concepts: {concepts})')
    print("This is a ranked review list, not a filtered answer — a low score can still")
    print("be a real hit (e.g. a company name with no literal keyword in it, referenced")
    print("only via one matched word); a high score is not a guarantee of fit either.\n")

    print(f"=== Matched ALL {n_concepts} concepts ({len(full_matches)}) ===\n")
    for score, matched, snippets, p in full_matches[:limit]:
        print(f"— {p['name']}")
        if p["company"] or p["position"]:
            print(f"    {p['position']}" + (f" at {p['company']}" if p["company"] else ""))
        evidence = []
        if p["met_in_person"]:
            evidence.append("met in person")
        if p["has_vault_note"]:
            evidence.append("has vault note")
        if p["message_count"]:
            evidence.append(f"{p['message_count']} messages")
        if p["tier_override"]:
            evidence.append(f"tier_override={p['tier_override']}")
        if evidence:
            print(f"    evidence: {', '.join(evidence)}  sources: {p['sources']}")
        for concept, variant, snippet in snippets:
            label = f'"{variant}"' if variant != concept else f'"{concept}"'
            print(f"    matched {label}: ...{snippet}...")
        print()
    if len(full_matches) > limit:
        print(f"... and {len(full_matches) - limit} more full matches below the display limit\n")

    if partial_matches:
        print(f"=== Matched SOME but not all concepts ({len(partial_matches)}) — lower confidence, name + matched terms only ===\n")
        for score, matched, snippets, p in partial_matches[:limit]:
            print(f"— {p['name']} [{score}/{n_concepts}]: matched {matched}")
        if len(partial_matches) > limit:
            print(f"... and {len(partial_matches) - limit} more partial matches (--limit to see more)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    search(args.query, args.limit)
