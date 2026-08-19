"""
Step 1: parse Connections.csv, Invitations.csv, and messages.csv from your
LinkedIn "Complete" data export into intermediate JSON files.

Run this first. Requires config.py (copy config.example.py and fill it in).
"""
import csv, re, json, sys, os
from datetime import datetime
from collections import defaultdict

import config

csv.field_size_limit(sys.maxsize)

CONN_CSV = os.path.join(config.LINKEDIN_EXPORT_DIR, "Connections.csv")
INVITE_CSV = os.path.join(config.LINKEDIN_EXPORT_DIR, "Invitations.csv")
MSG_CSV = os.path.join(config.LINKEDIN_EXPORT_DIR, "messages.csv")
OUT = config.OUTPUT_DIR
os.makedirs(OUT, exist_ok=True)

ME_URL = config.MY_LINKEDIN_URL.strip().rstrip("/").lower() if config.MY_LINKEDIN_URL else None
if not ME_URL:
    print("ERROR: set MY_LINKEDIN_URL in config.py — your own LinkedIn profile URL, "
          "needed to tell your messages apart from everyone else's.")
    sys.exit(1)


def norm_url(u):
    if not u:
        return None
    u = u.strip().rstrip("/")
    u = re.sub(r"\?.*$", "", u)
    u = u.lower()
    return u


def norm_name(n):
    if not n:
        return ""
    n = re.sub(r"\s+", " ", n.strip())
    return n


# ---------- STEP: parse Connections.csv (skip preamble before the header row) ----------
connections = {}  # url -> record
name_to_urls = defaultdict(list)

with open(CONN_CSV, newline="", encoding="utf-8") as f:
    lines = f.readlines()

header_idx = None
for i, line in enumerate(lines):
    if line.startswith("First Name,Last Name"):
        header_idx = i
        break

if header_idx is None:
    print("ERROR: could not find Connections.csv header (expected a line starting 'First Name,Last Name')")
    sys.exit(1)

reader = csv.DictReader(lines[header_idx:])
conn_rows = 0
conn_parse_errors = 0
for row in reader:
    conn_rows += 1
    try:
        first = norm_name(row.get("First Name", ""))
        last = norm_name(row.get("Last Name", ""))
        url = norm_url(row.get("URL", ""))
        email = (row.get("Email Address") or "").strip()
        company = (row.get("Company") or "").strip()
        position = (row.get("Position") or "").strip()
        connected_on_raw = (row.get("Connected On") or "").strip()
        connected_on = None
        if connected_on_raw:
            try:
                connected_on = datetime.strptime(connected_on_raw, "%d %b %Y").date().isoformat()
            except ValueError:
                connected_on = connected_on_raw
        full = f"{first} {last}".strip()
        if not url:
            conn_parse_errors += 1
            continue
        rec = {
            "first_name": first,
            "last_name": last,
            "full_name": full,
            "linkedin_url": url,
            "email": email,
            "company": company,
            "position": position,
            "connected_on": connected_on,
        }
        connections[url] = rec
        name_to_urls[full.lower()].append(url)
    except Exception:
        conn_parse_errors += 1

print(f"Connections.csv: {conn_rows} rows read, {len(connections)} unique URLs, {conn_parse_errors} parse errors")

# ---------- STEP: parse Invitations.csv ----------
invite_rows = 0
invite_parse_errors = 0
invite_matched = 0
invite_by_url = {}

with open(INVITE_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        invite_rows += 1
        try:
            direction = (row.get("Direction") or "").strip()
            note = (row.get("Message") or "").strip()
            sent_at_raw = (row.get("Sent At") or "").strip()
            inviter = norm_url(row.get("inviterProfileUrl", ""))
            invitee = norm_url(row.get("inviteeProfileUrl", ""))
            counterpart = None
            if inviter and inviter != ME_URL:
                counterpart = inviter
            elif invitee and invitee != ME_URL:
                counterpart = invitee
            if not counterpart:
                invite_parse_errors += 1
                continue
            sent_at = None
            if sent_at_raw:
                try:
                    sent_at = datetime.strptime(sent_at_raw, "%m/%d/%y, %I:%M %p").date().isoformat()
                except ValueError:
                    sent_at = sent_at_raw
            if counterpart in connections:
                invite_matched += 1
            invite_by_url[counterpart] = {
                "direction": direction,
                "note": note,
                "sent_at": sent_at,
            }
        except Exception:
            invite_parse_errors += 1

print(f"Invitations.csv: {invite_rows} rows read, {invite_matched} matched to a connection URL, {invite_parse_errors} parse errors")

# ---------- STEP: parse messages.csv (streaming aggregation) ----------
msg_rows = 0
msg_parse_errors = 0
msg_group_skipped = 0
msg_no_url_skipped = 0
msg_matched_rows = 0

msg_agg = defaultdict(lambda: {
    "total": 0, "sent_by_me": 0, "sent_by_them": 0,
    "first_date": None, "last_date": None,
    "sample_content": []  # short list kept for the later LLM summarization pass
})


def strip_html(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    s = re.sub(r"&#39;", "'", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


with open(MSG_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        msg_rows += 1
        try:
            sender_url = norm_url(row.get("SENDER PROFILE URL", ""))
            recipient_urls_raw = (row.get("RECIPIENT PROFILE URLS") or "").strip()
            recipient_urls = [norm_url(u) for u in recipient_urls_raw.split(",") if u.strip()]
            date_raw = (row.get("DATE") or "").strip()
            content = row.get("CONTENT") or ""

            date_iso = None
            if date_raw:
                try:
                    date_iso = datetime.strptime(date_raw, "%Y-%m-%d %H:%M:%S %Z" if "UTC" in date_raw else "%Y-%m-%d %H:%M:%S").date().isoformat()
                except ValueError:
                    try:
                        date_iso = datetime.strptime(date_raw.replace(" UTC", ""), "%Y-%m-%d %H:%M:%S").date().isoformat()
                    except ValueError:
                        date_iso = None

            is_from_me = sender_url == ME_URL
            is_to_me = ME_URL in recipient_urls if recipient_urls else False

            if not sender_url and not recipient_urls:
                msg_no_url_skipped += 1
                continue

            if is_from_me:
                counterpart_urls = [u for u in recipient_urls if u and u != ME_URL]
            elif is_to_me:
                counterpart_urls = [sender_url] if sender_url else []
            else:
                msg_no_url_skipped += 1
                continue

            counterpart_urls = [u for u in counterpart_urls if u]
            if not counterpart_urls:
                msg_no_url_skipped += 1
                continue

            if len(counterpart_urls) > 1:
                # group conversation — skip per-person attribution to avoid false signal
                msg_group_skipped += 1
                continue

            cp = counterpart_urls[0]
            msg_matched_rows += 1
            agg = msg_agg[cp]
            agg["total"] += 1
            if is_from_me:
                agg["sent_by_me"] += 1
            else:
                agg["sent_by_them"] += 1
            if date_iso:
                if agg["first_date"] is None or date_iso < agg["first_date"]:
                    agg["first_date"] = date_iso
                if agg["last_date"] is None or date_iso > agg["last_date"]:
                    agg["last_date"] = date_iso
            plain = strip_html(content)
            if plain and len(agg["sample_content"]) < 40:
                agg["sample_content"].append({"date": date_iso, "from_me": is_from_me, "text": plain[:500]})
        except Exception:
            msg_parse_errors += 1

print(f"messages.csv: {msg_rows} rows read, {msg_matched_rows} matched to single counterpart, "
      f"{msg_group_skipped} group-conversation rows skipped, {msg_no_url_skipped} rows with no resolvable URL skipped, "
      f"{msg_parse_errors} parse errors")
print(f"messages.csv: {len(msg_agg)} unique counterpart URLs with message activity")

msg_matched_to_connection = sum(1 for u in msg_agg if u in connections)
print(f"messages.csv: {msg_matched_to_connection} of those counterpart URLs match a connection in Connections.csv")

with open(f"{OUT}/step1_connections.json", "w") as f:
    json.dump(connections, f)
with open(f"{OUT}/step1_invites.json", "w") as f:
    json.dump(invite_by_url, f)
with open(f"{OUT}/step1_messages.json", "w") as f:
    json.dump(msg_agg, f)
with open(f"{OUT}/step1_name_to_urls.json", "w") as f:
    json.dump(name_to_urls, f)

print("Saved intermediate JSON files to", OUT)
