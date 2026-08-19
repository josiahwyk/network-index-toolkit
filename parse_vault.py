"""
Step 2b: match Obsidian vault notes to your LinkedIn connections — dedicated
"Chat with X" style notes (word-boundary full-name match, promotes to Tier 1),
and journal/diary mentions (recorded as a source, does NOT promote to Tier 1
on its own). Run after parse.py. Skips entirely if config.VAULT_DIR is None.
"""
import json, re, os
from collections import defaultdict

import config

OUT = config.OUTPUT_DIR

if not config.VAULT_DIR:
    print("VAULT_DIR not set in config.py — skipping vault matching.")
    for name in ["step2_vault_dedicated_matches", "step2_vault_dedicated_ambiguous",
                 "step2_vault_dedicated_unmatched", "step2_journal_mentions"]:
        with open(f"{OUT}/{name}.json", "w") as f:
            json.dump({} if "matches" in name or "mentions" in name else [], f)
    raise SystemExit(0)

VAULT = config.VAULT_DIR
JOURNAL_DIR = os.path.join(VAULT, config.JOURNAL_SUBFOLDER) if config.JOURNAL_SUBFOLDER else None

with open(f"{OUT}/step1_connections.json") as f:
    connections = json.load(f)
with open(f"{OUT}/step1_name_to_urls.json") as f:
    name_to_urls = json.load(f)

# ---------- dedicated note filenames: "Chat with X", "Caught up with X", "Coffee with X", "Catch up with X" ----------
# Customize this pattern to match your own note-naming convention if different.
PATTERN = re.compile(r"(chat|coffee|caught up|catch[- ]?up)\s+with\s+(.+)", re.IGNORECASE)

dedicated_note_matches = defaultdict(list)
dedicated_note_ambiguous = []
dedicated_note_unmatched = []

all_md_files = []
for root, dirs, files in os.walk(VAULT):
    if "/.git" in root or "/.obsidian" in root or "/.smart-connections" in root:
        continue
    for fn in files:
        if fn.endswith(".md"):
            all_md_files.append(os.path.join(root, fn))


def clean_extracted(raw):
    raw = raw.strip()
    for sep in [" (", " - ", " – ", " about ", " to chat", " this morning", " re:", " – "]:
        idx = raw.find(sep)
        if idx > 0:
            raw = raw[:idx]
    return raw.rstrip(".").strip()


def candidates_for(name_str):
    key = re.sub(r"\s+", " ", name_str.strip().lower())
    if key in name_to_urls:
        return name_to_urls[key]
    tokens = key.split(" ")
    if len(tokens) > 2:
        key2 = " ".join(tokens[:2])
        if key2 in name_to_urls:
            return name_to_urls[key2]
    return []


for path in all_md_files:
    fn = os.path.basename(path)[:-3]
    m = PATTERN.search(fn)
    if not m:
        continue
    extracted = clean_extracted(m.group(2))
    if not extracted:
        continue
    rel = os.path.relpath(path, VAULT)
    cands = candidates_for(extracted)
    if len(cands) == 1:
        dedicated_note_matches[cands[0]].append({"file": rel, "extracted_name": extracted})
    elif len(cands) > 1:
        dedicated_note_ambiguous.append({"file": rel, "extracted_name": extracted, "candidate_urls": cands})
    else:
        dedicated_note_unmatched.append({"file": rel, "extracted_name": extracted})

print(f"Vault dedicated-note filenames: {len(all_md_files)} total md files scanned")
print(f"Vault dedicated-note filenames: {len(dedicated_note_matches)} connections matched to a dedicated note")
print(f"Vault dedicated-note filenames: {len(dedicated_note_ambiguous)} files with ambiguous name (multiple candidates)")
print(f"Vault dedicated-note filenames: {len(dedicated_note_unmatched)} files with no matching connection (informational, not linked)")

# ---------- journal mentions: full-name substring scan ----------
journal_files = []
if JOURNAL_DIR and os.path.isdir(JOURNAL_DIR):
    for fn in os.listdir(JOURNAL_DIR):
        if fn.endswith(".md"):
            journal_files.append(os.path.join(JOURNAL_DIR, fn))

name_patterns = []
for full_name_lower, urls in name_to_urls.items():
    tokens = full_name_lower.split(" ")
    if len(tokens) < 2 or not all(tokens):
        continue
    if len(urls) != 1:
        continue  # skip ambiguous common names for substring scanning — too risky
    pat = re.compile(r"\b" + re.escape(full_name_lower) + r"\b", re.IGNORECASE)
    name_patterns.append((full_name_lower, urls[0], pat))

journal_mentions = defaultdict(list)
journal_files_scanned = 0
for jf in journal_files:
    journal_files_scanned += 1
    try:
        with open(jf, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception:
        continue
    rel = os.path.relpath(jf, VAULT)
    for full_name_lower, url, pat in name_patterns:
        if pat.search(text):
            journal_mentions[url].append({"file": rel})

print(f"Journal scan: {journal_files_scanned} files scanned")
print(f"Journal scan: {len(journal_mentions)} connections mentioned by full name")

with open(f"{OUT}/step2_vault_dedicated_matches.json", "w") as f:
    json.dump(dedicated_note_matches, f)
with open(f"{OUT}/step2_vault_dedicated_ambiguous.json", "w") as f:
    json.dump(dedicated_note_ambiguous, f)
with open(f"{OUT}/step2_vault_dedicated_unmatched.json", "w") as f:
    json.dump(dedicated_note_unmatched, f)
with open(f"{OUT}/step2_journal_mentions.json", "w") as f:
    json.dump(journal_mentions, f)
