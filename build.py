"""
Step 3: merge parsed sources, expose raw evidence, print a summary report.

No computed tier or relationship score. This step deliberately does NOT rank
or classify people — testing showed message-count-based tiering conflates
"we exchanged pleasantries once" with "this is a real relationship" (e.g.
someone with 8 one-off messages landing in the same bucket as someone with
162 messages spanning years). Instead every person's raw evidence is exposed
as frontmatter fields in generate.py, and you judge relationship strength
yourself — optionally recording that judgment in `tier_override`, which is
carried forward untouched on every re-run.

STOP AND READ THE REPORT before running generate.py. If "significant contact"
(the pool selected for LLM summaries in prepare_summaries_input.py) comes
back wildly high or low relative to your sense of your own network, something
may be wrong with the matching — cheaper to catch here than after writing
thousands of files.

"Significant contact" (used only to decide who gets an LLM-written
Context/Conversation summary — NOT written to the file, NOT a tier):
  a calendar event, OR a dedicated vault note, OR 5+ two-way messages.
This is the same bar the old Tier 1 rule used; it's kept only to bound the
(fairly expensive) summary-writing step to people with real signal, not as
a relationship judgment.
"""
import json
from collections import defaultdict

import config

OUT = config.OUTPUT_DIR


def load(name):
    with open(f"{OUT}/{name}") as f:
        return json.load(f)


connections = load("step1_connections.json")
invites = load("step1_invites.json")
messages = load("step1_messages.json")
name_to_urls = load("step1_name_to_urls.json")
calendar_matches = load("step2_calendar_matches.json")
calendar_ambiguous = load("step2_calendar_ambiguous.json")
vault_dedicated = load("step2_vault_dedicated_matches.json")
vault_dedicated_ambiguous = load("step2_vault_dedicated_ambiguous.json")
journal_mentions = load("step2_journal_mentions.json")

people = {}
for url, conn in connections.items():
    p = dict(conn)
    p["invitation"] = invites.get(url)
    p["messages"] = messages.get(url)
    p["calendar_events"] = calendar_matches.get(url, [])
    p["dedicated_notes"] = vault_dedicated.get(url, [])
    p["journal_mentions"] = journal_mentions.get(url, [])

    sources = ["linkedin"]
    if p["messages"]:
        sources.append("messages")
    if p["calendar_events"]:
        sources.append("calendar")
    if p["dedicated_notes"] or p["journal_mentions"]:
        sources.append("vault")
    p["sources"] = sources

    msg = p["messages"]
    two_way = bool(msg and msg["sent_by_me"] > 0 and msg["sent_by_them"] > 0)
    total_msg = msg["total"] if msg else 0
    has_calendar = len(p["calendar_events"]) > 0
    has_dedicated_note = len(p["dedicated_notes"]) > 0

    # Raw evidence fields — no ranking, no judgment baked in.
    p["two_way"] = two_way
    p["met_in_person"] = has_calendar or has_dedicated_note
    p["has_vault_note"] = has_dedicated_note

    # Used only to bound the LLM summary-writing step — not written to the
    # file, not exposed as a tier.
    p["_significant"] = has_calendar or has_dedicated_note or (two_way and total_msg >= 5)

    people[url] = p

significant_count = sum(1 for p in people.values() if p["_significant"])
matched_messages = sum(1 for p in people.values() if p["messages"])
matched_calendar = sum(1 for p in people.values() if p["calendar_events"])
matched_invitations = sum(1 for p in people.values() if p["invitation"])
matched_vault = sum(1 for p in people.values() if p["dedicated_notes"] or p["journal_mentions"])
matched_dedicated_note_only = sum(1 for p in people.values() if p["dedicated_notes"])
matched_journal_only = sum(1 for p in people.values() if p["journal_mentions"])

print("=== TOTALS ===")
print(f"Total connections (people files to generate): {len(people)}")
print(f"'Significant contact' pool (drives LLM summary step only, not written to file): {significant_count}")
print()
print("=== MATCH COUNTS ===")
print(f"Matched on messages: {matched_messages}")
print(f"Matched on calendar: {matched_calendar}")
print(f"Matched on invitations: {matched_invitations}")
print(f"Matched on vault (dedicated note or journal mention): {matched_vault}")
print(f"  - via dedicated note file: {matched_dedicated_note_only}")
print(f"  - via journal mention: {matched_journal_only}")
print()
print("=== AMBIGUOUS MATCHES NEEDING REVIEW ===")
print(f"Calendar attendee names matching >1 connection: {len(calendar_ambiguous)}")
for name, events in calendar_ambiguous.items():
    cand_names = [connections[u]["full_name"] + " (" + connections[u].get("company", "") + ")" for u in events[0]["candidate_urls"]]
    print(f"  - '{name}' in {len(events)} event(s), candidates: {cand_names}")
print(f"Vault dedicated-note filenames matching >1 connection: {len(vault_dedicated_ambiguous)}")
for item in vault_dedicated_ambiguous:
    cand_names = [connections[u]["full_name"] + " (" + connections[u].get("company", "") + ")" for u in item["candidate_urls"]]
    print(f"  - file '{item['file']}' -> extracted '{item['extracted_name']}', candidates: {cand_names}")

with open(f"{OUT}/step3_people.json", "w") as f:
    json.dump(people, f)

print()
print("Saved step3_people.json — review the report above, then run generate.py")
