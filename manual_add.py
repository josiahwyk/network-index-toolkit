"""
One-off manual entry for an off-platform interaction (call, coffee, event —
anything NOT already captured by LinkedIn DMs, email, or calendar exports,
which are covered automatically by the other scripts).

Usage: edit the ENTRY dict below, then run:
    python3 manual_add.py

This writes/updates a record in manual_entries.json, keyed by the person's
LinkedIn URL if they already exist in the index (matched by exact name,
disambiguated by company if the name is ambiguous), or by a synthetic
"manual:<name>" key if they're a genuinely new contact with no LinkedIn
connection on file. Re-run generate.py afterwards to materialize/update the
file — the idempotency/manual-notes guarantees still hold.

Write SUMMARY as a short written summary of the interaction (skip
scheduling/pleasantries, keep what you actually discussed/do) — never a raw
paste of the conversation.
"""
import json, os, sys

import config

OUT = config.OUTPUT_DIR

# --- EDIT THIS BLOCK PER ENTRY ---
ENTRY = {
    "full_name": "",       # required, exact full name as it should appear
    "company": "",         # optional
    "position": "",        # optional
    "date": "",            # required, YYYY-MM-DD, date of the interaction
    "summary": "",         # required, one written summary line/paragraph
    "manual_context": "",  # optional, short addition to the Context section
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
    if not entry["full_name"] or not entry["date"] or not entry["summary"]:
        print("ERROR: full_name, date, and summary are required.")
        sys.exit(1)

    manual_path = f"{OUT}/manual_entries.json"
    if os.path.exists(manual_path):
        with open(manual_path) as f:
            manual_entries = json.load(f)
    else:
        manual_entries = {}

    matched_url = find_match(entry["full_name"], entry.get("company", ""))
    key = matched_url if matched_url else f"manual:{entry['full_name'].strip()}"

    if key not in manual_entries:
        manual_entries[key] = {
            "full_name": entry["full_name"],
            "company": entry.get("company", ""),
            "position": entry.get("position", ""),
            "manual_meetings": [],
            "manual_context": "",
        }

    manual_entries[key]["manual_meetings"].append({
        "date": entry["date"],
        "summary": entry["summary"],
    })
    if entry.get("manual_context"):
        existing = manual_entries[key].get("manual_context", "")
        manual_entries[key]["manual_context"] = (
            f"{existing} {entry['manual_context']}".strip() if existing else entry["manual_context"]
        )

    with open(manual_path, "w") as f:
        json.dump(manual_entries, f, indent=2)

    status = "matched existing connection" if matched_url else "new contact, no LinkedIn record — synthetic entry"
    print(f"Logged manual interaction for {entry['full_name']} ({status}, key={key})")
    print("Run generate.py to materialize the change.")


if __name__ == "__main__":
    main(ENTRY)
