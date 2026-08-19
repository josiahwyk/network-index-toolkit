"""
Step 5: idempotent generation of one markdown file per connection.

Safe to re-run any time you have a fresh export: new connections get new
files, connections whose source data changed get updated (auto-generated
zone only — your manual notes below the marker are always preserved
byte-for-byte), and unchanged connections are skipped entirely, not
rewritten. Prints "X new, Y updated, Z unchanged" every run.

Requires master_summaries.json (see prepare_summaries_input.py) — if that
file doesn't exist yet, Context/Conversation summary will just be blank for
everyone, which is fine to run with while you're still iterating.

No computed tier. Every file exposes raw evidence as frontmatter fields
(message_count, messages_two_way, first_contact, last_contact,
met_in_person, has_vault_note, invitation_direction) and you judge
relationship strength yourself. `tier_override` is yours to set by hand in
any file's frontmatter — it lives in the auto-generated block like the rest
of the frontmatter, but is a special case: every re-run reads the existing
file's current tier_override value first and carries it forward unchanged,
so your manual judgment is never overwritten. Leave it blank to record
nothing.
"""
import json, os, re
import yaml

import config

OUT = config.OUTPUT_DIR
VAULT = config.VAULT_DIR
NETWORK_DIR = os.path.join(VAULT, config.NETWORK_SUBFOLDER)

MARKER = "<!-- MANUAL NOTES BELOW -->"

with open(f"{OUT}/step3_people.json") as f:
    people = json.load(f)

summaries_path = f"{OUT}/master_summaries.json"
if os.path.exists(summaries_path):
    with open(summaries_path) as f:
        summaries = json.load(f)
else:
    print("No master_summaries.json found — Context/Conversation summary will be blank. "
          "See prepare_summaries_input.py.")
    summaries = {}

# Manual entries: off-platform interactions (calls, coffees, events) logged
# via manual_add.py. Keyed by matched LinkedIn URL if the person already
# exists, or a synthetic "manual:<name>" key for people with no LinkedIn
# connection on file at all.
manual_path = f"{OUT}/manual_entries.json"
if os.path.exists(manual_path):
    with open(manual_path) as f:
        manual_entries = json.load(f)
else:
    manual_entries = {}

# LinkedIn recommendations (given/received) — literal testimonial text,
# matched by exact name. Does NOT change tier (that rule is intentionally
# frozen); just adds a source tag + a real quote to Context.
recs_path = f"{OUT}/step2_recommendations.json"
if os.path.exists(recs_path):
    with open(recs_path) as f:
        recommendations = json.load(f)
else:
    recommendations = {}

for url, entries in recommendations.items():
    if url in people:
        if "recommendation" not in people[url]["sources"]:
            people[url]["sources"] = people[url]["sources"] + ["recommendation"]

for key, m in manual_entries.items():
    if key in people:
        p = people[key]
        p["manual_meetings"] = m.get("manual_meetings", [])
        if "manual" not in p["sources"]:
            p["sources"] = p["sources"] + ["manual"]
    else:
        # Synthetic person: exists only through manually-logged interactions,
        # no LinkedIn connection on file. A real off-platform interaction is
        # meeting-equivalent evidence, so met_in_person=True.
        people[key] = {
            "full_name": m["full_name"],
            "linkedin_url": "",
            "company": m.get("company") or "",
            "position": m.get("position") or "",
            "connected_on": "",
            "messages": None,
            "two_way": False,
            "met_in_person": True,
            "has_vault_note": False,
            "invitation": None,
            "sources": ["manual"],
            "calendar_events": [],
            "dedicated_notes": [],
            "journal_mentions": [],
            "manual_meetings": m.get("manual_meetings", []),
        }

# Load the existing filename registry so identity (URL -> filename) is stable
# across runs. New URLs get new filenames; URLs seen before keep the same
# filename forever, even if their name changes in a later export.
registry_path = f"{OUT}/step4_url_to_filename.json"
if os.path.exists(registry_path):
    with open(registry_path) as f:
        url_to_filename = json.load(f)
else:
    url_to_filename = {}

os.makedirs(NETWORK_DIR, exist_ok=True)

INVALID_CHARS = r'[\\/:*?"<>|]'


def sanitize(s):
    s = re.sub(INVALID_CHARS, "-", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- assign filenames: keep existing registry entries untouched, only
# --- generate new filenames for URLs not already in the registry ---
used_filenames = {fn.lower() for fn in url_to_filename.values()}

name_counts = {}
for p in people.values():
    name_counts[p["full_name"]] = name_counts.get(p["full_name"], 0) + 1

ordered = sorted(people.items(), key=lambda kv: kv[1]["full_name"].lower())

new_urls = [url for url, p in ordered if url not in url_to_filename]

for url in new_urls:
    p = people[url]
    base = p["full_name"].strip() or "Unknown"
    if name_counts.get(base, 0) > 1:
        disambig = p.get("company") or url.rstrip("/").split("/")[-1]
        fname = f"{base} ({disambig})"
    else:
        fname = base
    fname = sanitize(fname)
    final = fname
    n = 2
    while final.lower() in used_filenames:
        final = f"{fname} ({n})"
        n += 1
    used_filenames.add(final.lower())
    url_to_filename[url] = final + ".md"


def build_frontmatter(p, tier_override):
    return {
        "name": p["full_name"],
        "linkedin_url": p.get("linkedin_url") or "",
        "company": p.get("company") or "",
        "position": p.get("position") or "",
        "connected": p.get("connected_on") or "",
        "first_contact": (p["messages"]["first_date"] if p["messages"] and p["messages"].get("first_date") else "") or "",
        "last_contact": (p["messages"]["last_date"] if p["messages"] and p["messages"].get("last_date") else "") or "",
        "message_count": p["messages"]["total"] if p["messages"] else 0,
        "messages_two_way": p["two_way"],
        "met_in_person": p.get("met_in_person", False),
        "has_vault_note": p.get("has_vault_note", False),
        "invitation_direction": (p["invitation"]["direction"].lower() if p["invitation"] and p["invitation"].get("direction") else ""),
        "tier_override": tier_override or "",
        "sources": p["sources"],
    }


def read_existing_tier_override(path):
    """Read tier_override from a file's current frontmatter, if any, so it
    survives being overwritten on re-run. Returns "" if the file doesn't
    exist yet or has no frontmatter/tier_override."""
    if not os.path.exists(path):
        return ""
    try:
        with open(path, encoding="utf-8") as f:
            existing = f.read()
        if not existing.startswith("---"):
            return ""
        _, _, rest = existing.partition("---\n")
        fm_text, sep, _ = rest.partition("\n---")
        if not sep:
            return ""
        fm = yaml.safe_load(fm_text) or {}
        return fm.get("tier_override") or ""
    except Exception:
        return ""


def build_auto_zone(url, p, tier_override):
    """Everything that is machine-generated: frontmatter through Notes.
    Returned WITHOUT a trailing newline so callers control spacing."""
    fm = build_frontmatter(p, tier_override)
    fm_yaml = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=None)

    position_line = ""
    if p.get("position") and p.get("company"):
        position_line = f"{p['position']} at {p['company']}"
    elif p.get("position"):
        position_line = p["position"]
    elif p.get("company"):
        position_line = p["company"]

    s = summaries.get(url, {})
    ctx = (s.get("context") or "").strip()
    conv = (s.get("conversation_summary") or "").strip()

    manual_ctx = (manual_entries.get(url, {}).get("manual_context") or "").strip()
    if manual_ctx:
        ctx = f"{ctx} {manual_ctx}".strip() if ctx else manual_ctx

    rec_lines = []
    for r in recommendations.get(url, []):
        text = " ".join((r.get("text") or "").split())
        if not text:
            continue
        attribution = f"{r.get('title') or ''} at {r.get('company')}".strip() if r.get("company") else ""
        date_part = (r.get("date") or "").split(",")[0].strip()
        tag = f"({attribution}{', ' + date_part if date_part else ''})".strip()
        if r["direction"] == "given":
            rec_lines.append(f'You wrote them a LinkedIn recommendation {tag}: "{text}"')
        else:
            rec_lines.append(f'They wrote you a LinkedIn recommendation {tag}: "{text}"')
    if rec_lines:
        rec_block = " ".join(rec_lines)
        ctx = f"{ctx} {rec_block}".strip() if ctx else rec_block

    meetings_lines = []
    for ev in p.get("calendar_events", []):
        date = ev.get("date") or "Unknown date"
        summ = ev.get("summary") or "(no title)"
        meetings_lines.append(f"- {date} — {summ}")
    for ev in p.get("manual_meetings", []):
        date = ev.get("date") or "Unknown date"
        summ = ev.get("summary") or "(no title)"
        meetings_lines.append(f"- {date} — {summ} (manually logged)")
    meetings_block = "\n".join(meetings_lines)

    notes_lines = []
    for n in p.get("dedicated_notes", []):
        base = os.path.basename(n["file"])[:-3]
        notes_lines.append(f"- [[{base}]]")
    for n in p.get("journal_mentions", []):
        base = os.path.basename(n["file"])[:-3]
        link = f"- [[{base}]]"
        if link not in notes_lines:
            notes_lines.append(link)
    notes_block = "\n".join(notes_lines)

    # Match legacy spacing exactly: an empty Context/Conversation summary
    # section has two blank lines before the next header (no content line);
    # a filled one has the content surrounded by a single blank line each side.
    middle = "## Context\n\n"
    middle += (ctx + "\n\n") if ctx else "\n"
    middle += "## Conversation summary\n\n"
    middle += (conv + "\n\n") if conv else "\n"
    middle += "## Meetings\n\n"
    middle += meetings_block

    return f"""---
{fm_yaml}---

# {p['full_name']}
{position_line}

{middle}

## Notes

{notes_block}"""


new_count = 0
updated_count = 0
unchanged_count = 0
new_names = []
updated_names = []

for url, p in ordered:
    filename = url_to_filename[url]
    path = os.path.join(NETWORK_DIR, filename)
    tier_override = read_existing_tier_override(path)
    auto_zone = build_auto_zone(url, p, tier_override)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            existing = f.read()
        if MARKER in existing:
            existing_auto, _, existing_manual = existing.partition(MARKER)
            manual_tail = MARKER + existing_manual
        else:
            # No marker yet — treat everything as auto-zone, start a fresh manual zone.
            existing_auto = existing
            manual_tail = f"{MARKER}\n\n## My notes\n\n"

        if existing_auto.rstrip("\n") == auto_zone.rstrip("\n"):
            unchanged_count += 1
            continue

        new_content = auto_zone.rstrip("\n") + "\n\n" + manual_tail.lstrip("\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        updated_count += 1
        updated_names.append(p["full_name"])
    else:
        new_content = auto_zone.rstrip("\n") + "\n\n" + MARKER + "\n\n## My notes\n\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)
        new_count += 1
        new_names.append(p["full_name"])

with open(registry_path, "w") as f:
    json.dump(url_to_filename, f)

print(f"{new_count} new, {updated_count} updated, {unchanged_count} unchanged")
if new_names:
    print(f"\nNew ({len(new_names)}):")
    for n in new_names[:50]:
        print(f"  - {n}")
    if len(new_names) > 50:
        print(f"  ... and {len(new_names) - 50} more")
if updated_names:
    print(f"\nUpdated ({len(updated_names)}):")
    for n in updated_names[:50]:
        print(f"  - {n}")
    if len(updated_names) > 50:
        print(f"  ... and {len(updated_names) - 50} more")
