"""
Copy this file to config.py and fill in your own paths/details.
config.py is gitignored — it will contain paths specific to your machine,
never commit it.
"""

# Folder that holds your unzipped LinkedIn "Complete" data export
# (Settings > Data Privacy > Get a copy of your data > "The works").
# Must contain: Connections.csv, Invitations.csv, messages.csv,
# and optionally Recommendations_Received.csv / Recommendations_Given.csv.
LINKEDIN_EXPORT_DIR = "/path/to/your/LinkedIn Export"

# Path to a Google Calendar .ics export (Google Takeout > Calendar).
# Set to None to skip calendar matching entirely.
CALENDAR_ICS_PATH = "/path/to/your/calendar.ics"

# Path to your Obsidian vault (or any folder of markdown notes).
# Set to None to skip vault matching entirely.
VAULT_DIR = "/path/to/your/Obsidian Vault"

# Subfolder inside VAULT_DIR where generated person-files are written.
NETWORK_SUBFOLDER = "Network"

# Subfolder inside VAULT_DIR containing your recurring journal/diary notes,
# scanned for full-name mentions (journal mentions are a source, not a
# tier-1 trigger on their own — only calendar events and dedicated notes are).
# Set to None to skip journal scanning.
JOURNAL_SUBFOLDER = "Journal"

# Your own LinkedIn profile URL — used to tell your own messages/invitations
# apart from everyone else's in the export. Find it on your own profile page.
MY_LINKEDIN_URL = "https://www.linkedin.com/in/your-handle"

# Your own name(s) as they appear as a calendar attendee — used to exclude
# yourself from attendee matching. Lowercase.
MY_NAMES = {"your name", "your full name"}

# Working/intermediate-file directory (safe to gitignore entirely).
OUTPUT_DIR = "./output"
