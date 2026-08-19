"""
Step 4 (the step that needs an LLM, not just a script): dump every
"significant contact" person's actual message/note/calendar content into one
JSON file, ready to hand to Claude Code, a Claude Cowork session, or the
Claude API. "Significant contact" = a calendar event, OR a dedicated vault
note, OR 5+ two-way messages — the same bar the old Tier 1 rule used, kept
here only to bound this step to people with real signal. It is not written
to the generated files and is not a relationship judgment.

Why this step can't be scripted: writing an honest, non-invented summary of
what you actually discussed with someone requires reading and understanding
real conversation content — that's LLM work, not string matching. This
toolkit gets you the raw material; you (or your coding agent) still have to
read it and write it.

Output: summaries_input.json — feed this to your LLM of choice with a prompt
like:

  "For each person below, write a 1-3 sentence 'context' (who they are /
  what they do, beyond frontmatter) and a 1-3 sentence 'conversation_summary'
  (what you actually discussed — referrals, expertise, favours). Skip pure
  scheduling/pleasantries. Never invent anything not in the source text. If
  there's nothing substantive, leave both fields as empty strings — don't pad.
  Return JSON: {url: {"context": "...", "conversation_summary": "..."}}."

Save the LLM's output as master_summaries.json in OUTPUT_DIR, then run
generate.py.
"""
import json, os

import config

OUT = config.OUTPUT_DIR

with open(f"{OUT}/step3_people.json") as f:
    people = json.load(f)

out = {}
for url, p in people.items():
    if not p.get("_significant"):
        continue
    entry = {
        "full_name": p["full_name"],
        "company": p.get("company") or "",
        "position": p.get("position") or "",
        "sources": p.get("sources", []),
    }
    m = p.get("messages")
    if m and m.get("sample_content"):
        entry["messages"] = [
            {"date": mm["date"], "from_me": mm["from_me"], "text": mm["text"]}
            for mm in m["sample_content"]
        ]
    if p.get("dedicated_notes"):
        entry["dedicated_notes"] = [n["file"] for n in p["dedicated_notes"]]
    if p.get("journal_mentions"):
        entry["journal_mentions"] = [n["file"] for n in p["journal_mentions"]]
    if p.get("calendar_events"):
        entry["calendar_events"] = p["calendar_events"]
    out[url] = entry

with open(f"{OUT}/summaries_input.json", "w") as f:
    json.dump(out, f, indent=2)

print(f"Wrote {len(out)} Tier 1 people to {OUT}/summaries_input.json")
print("Hand this to an LLM (see the docstring at the top of this file for the prompt),")
print(f"save its output as {OUT}/master_summaries.json, then run generate.py")
