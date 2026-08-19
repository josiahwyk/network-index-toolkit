"""
Step 2a: match Google Calendar attendees to your LinkedIn connections by
exact display-name match. Run after parse.py. Skips entirely if
config.CALENDAR_ICS_PATH is None.

Requires the `icalendar` package: pip install icalendar
"""
import json, re, os
from collections import defaultdict

import config

OUT = config.OUTPUT_DIR

if not config.CALENDAR_ICS_PATH:
    print("CALENDAR_ICS_PATH not set in config.py — skipping calendar matching.")
    with open(f"{OUT}/step2_calendar_matches.json", "w") as f:
        json.dump({}, f)
    with open(f"{OUT}/step2_calendar_ambiguous.json", "w") as f:
        json.dump({}, f)
    raise SystemExit(0)

from icalendar import Calendar

with open(f"{OUT}/step1_connections.json") as f:
    connections = json.load(f)
with open(f"{OUT}/step1_name_to_urls.json") as f:
    name_to_urls = json.load(f)

MY_NAMES = {n.lower() for n in config.MY_NAMES}


def norm_name(n):
    if not n:
        return ""
    return re.sub(r"\s+", " ", str(n).strip())


with open(config.CALENDAR_ICS_PATH, "rb") as f:
    cal = Calendar.from_ical(f.read())

total_events = 0
events_with_attendees = 0
calendar_matches = defaultdict(list)
ambiguous_calendar = defaultdict(list)
unmatched_attendee_names = defaultdict(int)

for component in cal.walk():
    if component.name != "VEVENT":
        continue
    total_events += 1
    summary = str(component.get("summary", "") or "")
    dtstart = component.get("dtstart")
    date_iso = None
    if dtstart:
        try:
            d = dtstart.dt
            date_iso = d.date().isoformat() if hasattr(d, "date") else d.isoformat()
        except Exception:
            date_iso = None

    attendees = component.get("attendee")
    if attendees is None:
        continue
    if not isinstance(attendees, list):
        attendees = [attendees]
    events_with_attendees += 1

    seen_urls_this_event = set()
    for a in attendees:
        try:
            cn = a.params.get("CN")
        except Exception:
            cn = None
        if not cn:
            continue
        cn_norm = norm_name(cn).lower()
        if not cn_norm or cn_norm in MY_NAMES:
            continue
        candidate_urls = name_to_urls.get(cn_norm, [])
        if len(candidate_urls) == 1:
            url = candidate_urls[0]
            if url not in seen_urls_this_event:
                calendar_matches[url].append({"summary": summary, "date": date_iso})
                seen_urls_this_event.add(url)
        elif len(candidate_urls) > 1:
            ambiguous_calendar[cn_norm].append({"summary": summary, "date": date_iso, "candidate_urls": candidate_urls})
        else:
            unmatched_attendee_names[cn_norm] += 1

print(f"Calendar: {total_events} total VEVENTs, {events_with_attendees} with attendee lists")
print(f"Calendar: {len(calendar_matches)} connections matched via attendee name")
print(f"Calendar: {len(ambiguous_calendar)} distinct attendee names ambiguous (match >1 connection)")
print(f"Calendar: {len(unmatched_attendee_names)} distinct attendee names with no matching connection (informational only)")

with open(f"{OUT}/step2_calendar_matches.json", "w") as f:
    json.dump(calendar_matches, f)
with open(f"{OUT}/step2_calendar_ambiguous.json", "w") as f:
    json.dump(ambiguous_calendar, f)
