"""
One-off manual entry for:
  (a) an off-platform interaction (call, coffee, event) not already captured
      by LinkedIn DMs, email, or calendar exports, and/or
  (b) a correction to an EXISTING person's stale LinkedIn export data
      (company/position). Your LinkedIn export is a snapshot — someone's
      current job may not be what's on file, and no amount of search fixes
      a fact that was never written down anywhere in your data at all.

Usage: edit the ENTRY dict below, then run:
    python3 manual_add.py

At least one of (date+summary), manual_context, or (company_override /
position_override) must be set. full_name is always required.

Corrections only apply to an EXISTING matched connection (matched by exact
name, disambiguated by company if ambiguous) — there's nothing to correct on
a brand-new synthetic person, so overrides are ignored (with a warning) if no
match is found.

Why this goes through a script instead of just hand-editing the company/
position fields directly in the file, the way tier_override works:
tier_override is blank by default, so any non-blank value on disk is
unambiguously a manual entry. company/position are NOT blank by default —
they're recomputed from your LinkedIn export every run — so generate.py has
no way to tell "you edited this on purpose" apart from "your LinkedIn export
legitimately changed" just by diffing the file. Get that wrong and a real
job change silently stops ever being picked up again. Storing the override
explicitly in manual_entries.json avoids that ambiguity.

Claude writes SUMMARY as a short written summary of the interaction (skip
scheduling/pleasantries, keep what you actually discussed/do) — never a raw
paste of the conversation.
"""
import json, os, sys

import config

OUT = config.OUTPUT_DIR

# --- EDIT THIS BLOCK PER ENTRY ---
ENTRY = {
    "full_name": "",           # required, exact full name as it should appear
    "company": "",             # optional, only used if this becomes a NEW synthetic person
    "position": "",            # optional, only used if this becomes a NEW synthetic person
    "date": "",                # required if logging a meeting, else leave blank
    "summary": "",             # required if logging a meeting, else leave blank
    "manual_context": "",      # optional, short addition to the Context section
    "company_override": "",    # optional, corrects an EXISTING person's company
    "position_override": "",   # optional, corrects an EXISTING person's position
}
# --- END EDIT BLOCK ---


def find_match(full_name, company=""):
    with open(f"{OUT}/step3_people.json") as f:
        people = json.load(f)
    candidates = [
        (url, p) for url, p in people.items()
        if p["full_name"].strip().lower() == full_name.strip().lower()
    ]
    if len(candidates) == 1:
        return candidates[0][0]
    if len(candidates) > 1 and company:
        narrowed = [
            (url, p) for url, p in candidates
            if (p.get("company") or "").strip().lower() == company.strip().lower()
        ]
        if len(narrowed) == 1:
            return narrowed[0][0]
    return None


def main(entry):
    if not entry["full_name"]:
        print("ERROR: full_name is required.")
        sys.exit(1)

    has_meeting = bool(entry.get("date") or entry.get("summary"))
    if has_meeting and not (entry.get("date") and entry.get("summary")):
        print("ERROR: if logging a meeting, both date and summary are required.")
        sys.exit(1)

    has_override = bool(entry.get("company_override") or entry.get("position_override"))

    if not has_meeting and not entry.get("manual_context") and not has_override:
        print("ERROR: nothing to do — set date+summary, manual_context, or an override field.")
        sys.exit(1)

    manual_path = f"{OUT}/manual_entries.json"
    if os.path.exists(manual_path):
        with open(manual_path) as f:
            manual_entries = json.load(f)
    else:
        manual_entries = {}

    matched_url = find_match(entry["full_name"], entry.get("company", ""))
    key = matched_url if matched_url else f"manual:{entry['full_name'].strip()}"

    if has_override and not matched_url:
        print(f"WARNING: no existing connection matched for '{entry['full_name']}' — "
              f"override fields are ignored for new/synthetic people (nothing to correct).")

    if key not in manual_entries:
        manual_entries[key] = {
            "full_name": entry["full_name"],
            "company": entry.get("company", ""),
            "position": entry.get("position", ""),
            "manual_meetings": [],
            "manual_context": "",
            "company_override": "",
            "position_override": "",
        }

    if has_meeting:
        manual_entries[key]["manual_meetings"].append({
            "date": entry["date"],
            "summary": entry["summary"],
        })

    if entry.get("manual_context"):
        existing = manual_entries[key].get("manual_context", "")
        manual_entries[key]["manual_context"] = (
            f"{existing} {entry['manual_context']}".strip() if existing else entry["manual_context"]
        )

    if matched_url and has_override:
        if entry.get("company_override"):
            manual_entries[key]["company_override"] = entry["company_override"]
        if entry.get("position_override"):
            manual_entries[key]["position_override"] = entry["position_override"]

    with open(manual_path, "w") as f:
        json.dump(manual_entries, f, indent=2)

    status = "matched existing connection" if matched_url else "new contact, no LinkedIn record — synthetic entry"
    print(f"Logged manual entry for {entry['full_name']} ({status}, key={key})")
    if matched_url and has_override:
        applied = [k for k in ("company_override", "position_override") if entry.get(k)]
        print(f"  overrides set: {applied} — will apply on next generate.py run")
    print("Run generate.py to materialize the change.")


if __name__ == "__main__":
    main(ENTRY)
