"""
Optional step: parse LinkedIn Recommendations_Given.csv / Recommendations_Received.csv
(present in the "Complete" export, not the Basic one) and match them to your
connections by exact name. Where a match exists, the literal recommendation
text becomes real evidence in that person's Context section, and `recommendation`
is added to their sources. This does NOT change tier — see README.

Note: Positions.csv in the Complete export is YOUR OWN job history, not other
people's, so it's not useful here and isn't parsed by this toolkit.
"""
import csv, json, os, sys

import config

csv.field_size_limit(sys.maxsize)

OUT = config.OUTPUT_DIR
REC_RECEIVED = os.path.join(config.LINKEDIN_EXPORT_DIR, "Recommendations_Received.csv")
REC_GIVEN = os.path.join(config.LINKEDIN_EXPORT_DIR, "Recommendations_Given.csv")

with open(f"{OUT}/step1_name_to_urls.json") as f:
    name_to_urls = json.load(f)


def norm(n):
    return " ".join(n.strip().split()).lower()


matched = {}
total_rows = 0
zero_match = 0
multi_match = 0

for direction, path in [("received", REC_RECEIVED), ("given", REC_GIVEN)]:
    if not os.path.exists(path):
        continue
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            total_rows += 1
            full = norm(f"{row.get('First Name', '')} {row.get('Last Name', '')}")
            urls = name_to_urls.get(full, [])
            entry = {
                "direction": direction,
                "company": row.get("Company", ""),
                "title": row.get("Job Title", ""),
                "text": (row.get("Text", "") or "").strip(),
                "date": row.get("Creation Date", ""),
            }
            if len(urls) == 1:
                matched.setdefault(urls[0], []).append(entry)
            elif len(urls) == 0:
                zero_match += 1
            else:
                multi_match += 1

print(f"Recommendations: {total_rows} rows read, {len(matched)} unique people matched, "
      f"{zero_match} unmatched (name not in Connections.csv), {multi_match} ambiguous (skipped)")

with open(f"{OUT}/step2_recommendations.json", "w") as f:
    json.dump(matched, f, indent=2)
