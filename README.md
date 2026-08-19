# Network Index Toolkit

Turn your LinkedIn export (plus, optionally, a Google Calendar export and your
own notes) into a searchable index of your professional network — one
markdown file per person, sitting in your own notes app (e.g. Obsidian), that you or an LLM
can query later ("who do I know in IP law?", "who works in fintech in my network?", "who offers design services as a freelance in my network?").

Everything runs locally. Your export never leaves your machine, and nothing
here calls an external API except the one LLM step you choose to run
yourself (see Step 4 below).

## What this does and doesn't do

This is scripts, not an app. There's no UI. It:

1. Parses your LinkedIn export, calendar export, and notes vault with plain
   Python — no LLM involved, fully deterministic, safe to re-run.
2. Surfaces raw evidence per person (message count, first/last contact date,
   whether you've met in person, whether they have a dedicated vault note) as
   frontmatter fields. **No computed tier or relationship score.** Earlier
   versions tried scoring people into Tier 1/2/3 by message count and
   calendar/note presence — testing showed it conflates "we exchanged
   pleasantries once" with "this is a real relationship" (an old colleague
   with a burst of messages years ago outranked people met in person more
   recently). This toolkit shows you the evidence and lets you judge; you can
   record your own judgment per person in the `tier_override` field, which is
   yours to set and is never overwritten on re-run.
3. Hands you a JSON dump of "significant contact" people's actual
   message/note/calendar content (a calendar event, a dedicated vault note,
   or 5+ two-way messages — used only to bound this step to people with real
   signal, not a relationship judgment) for you to feed to an LLM of your
   choice to write short, accurate summaries. **This one step needs an LLM**
   — writing an honest summary of what you discussed with someone requires
   understanding real conversation content, which is judgment, not string
   matching. Bring your own (Claude Code, a Cowork session, the API, ChatGPT,
   whatever — copy the JSON in, copy the JSON out).
4. Writes one markdown file per person into your vault, with your own
   manually-added notes always preserved on re-runs.

## Requirements

- Python 3.9+
- `pip install -r requirements.txt`
- A LinkedIn "Complete" data export (Settings > Data Privacy > Get a copy of
  your data > "The works" — the Basic export is missing files this needs).
  LinkedIn emails you a download link within a day or so.
- Optional: a Google Calendar `.ics` export (Google Takeout > Calendar).
- Optional: a folder of markdown notes (Obsidian or any plain-text vault).

## Setup

```bash
pip install -r requirements.txt
cp config.example.py config.py
```

Edit `config.py`: point it at your unzipped LinkedIn export folder, your own
LinkedIn profile URL (needed to tell your own messages apart from
everyone else's), and optionally your calendar `.ics` path and vault path.
Every field is commented in `config.example.py`. `config.py` is gitignored —
it will contain paths specific to your machine, never commit it.

## Usage

Run in order:

```bash
python3 parse.py                  # Step 1: LinkedIn connections, invites, messages
python3 parse_calendar.py         # Step 2a: match calendar attendees (skips if not configured)
python3 parse_vault.py            # Step 2b: match vault notes + journal mentions (skips if not configured)
python3 parse_recommendations.py  # Step 2c: match LinkedIn recommendations (optional, skips if files absent)
python3 build.py                  # Step 3: merge, expose evidence — READ THE REPORT before continuing
```

`build.py` prints a report: total people, the "significant contact" count
(the pool that will get an LLM-written summary), match counts per source, and
any ambiguous name matches that need a look. **Stop and read it.** If the
significant-contact count comes back wildly high or low relative to your
sense of your own network, something may be wrong with the matching —
cheaper to catch here than after writing thousands of files.

```bash
python3 prepare_summaries_input.py
```

This writes `output/summaries_input.json` — every significant contact's raw
message/note/calendar content. Hand it to an LLM with the prompt in the
script's docstring, save the LLM's output as `output/master_summaries.json`,
then:

```bash
python3 generate.py
```

This writes the markdown files. Re-run any of the above any time you have a
fresh export — `generate.py` is idempotent: unchanged people are skipped
entirely, changed people get their auto-generated section updated, and
anything you've manually written below the `<!-- MANUAL NOTES BELOW -->`
marker in a file is preserved byte-for-byte. `tier_override` is also read
from the existing file and carried forward untouched, even though it lives in
the auto-generated frontmatter block.

To log an off-platform interaction (a call, coffee, event — anything not in
your LinkedIn export), edit the `ENTRY` dict at the top of `manual_add.py`
and run it, then re-run `generate.py`.

## File format

Each generated file looks like this:

```markdown
---
name: Jane Smith
linkedin_url: https://www.linkedin.com/in/janesmith
company: Acme Co
position: Head of Product
connected: '2019-03-12'
first_contact: '2020-01-05'
last_contact: '2024-11-02'
message_count: 14
messages_two_way: true
met_in_person: true
has_vault_note: false
invitation_direction: ''
tier_override: ''
sources: [linkedin, messages, calendar, recommendation]
---

# Jane Smith
Head of Product at Acme Co

## Context

[LLM-written, grounded in real messages/notes — never invented]

## Conversation summary

[LLM-written, grounded in real messages/notes — never invented]

## Meetings

- 2023-06-14 — Coffee catch-up

## Notes

- [[Chat with Jane Smith]]

<!-- MANUAL NOTES BELOW -->

## My notes

[anything you write here is yours — never touched by re-runs]
```

The frontmatter fields are structured and filterable in Obsidian (or any
tool that reads YAML frontmatter) — filter by `met_in_person`,
`tier_override`, `company`, `sources`, date ranges, etc.

## Limitations

- **Calendar matching is unreliable for most people.** It matches on the
  attendee's Common Name (CN) field in the .ics export, exact string match
  against your LinkedIn connections. In practice most calendar exports (this
  was true for mine — only ~1% of connections matched) have the CN field
  populated with a raw email address rather than a display name for most
  invitees, because that's what your calendar client captured at invite time.
  There's no reliable email-based fallback either, since most LinkedIn
  exports have an email on file for only a small fraction of connections.
  This is an upstream data-quality limit in both sources, not (currently) a
  bug this toolkit works around — if your calendar CN fields are more
  consistently populated with real names, matching will work much better for
  you.
- **No semantic/open-ended query layer.** This toolkit generates the files;
  it doesn't include a tool for answering loose questions like "who runs a
  marketing agency" or "who's senior in product." Regex/keyword search over
  company and position text will systematically miss anyone whose company
  name or title doesn't literally contain your search term (a company called
  "Zebra3" won't match a search for "agency" even if it is one). Answering
  those questions well needs an LLM reading the actual records, not string
  matching — not built here yet.
- Positions.csv in the LinkedIn export is your own job history, not other
  people's, so it isn't parsed.
- Name matching is exact-match with disambiguation by company where
  possible; genuinely ambiguous matches (same name, multiple candidates, no
  way to tell) are logged and skipped rather than guessed.
- The Context/Conversation summary step needs an LLM. This toolkit will not
  write those sections for you — see Step 4 above.
- No UI. This is a CLI workflow for people comfortable running Python
  scripts and editing a config file.

## Privacy

Nothing in this toolkit sends your data anywhere. `config.py`, your LinkedIn
export, and the `output/` working directory are all gitignored by default —
double-check before pushing your own fork anywhere public that you haven't
accidentally committed real data.

## License

MIT — see LICENSE.
