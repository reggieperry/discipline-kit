---
name: feedback-display-times-in-pt
description: "Display timestamps in the user's local timezone for human-facing summaries, not UTC; UTC is fine in raw tool output but rendered summaries should be local"
metadata: 
  node_type: memory
  type: feedback
  volatility: durable
---

When reporting status, phase timings, monitor output, or any timeline to the user, **display times in the user's local timezone** (e.g. `TZ=America/Los_Angeles date +"%H:%M:%S %Z"`), not UTC.

**Why:** The user reads the conversation in their local zone. UTC adds a mental conversion step on every status update. Raw tool output (machine-readable metadata fields, session log timestamps, CSV rows) is fine to leave in UTC since those are machine-readable and the user doesn't read them directly. The rendered summaries — tables, monitor lines, "current time" markers — get the user's attention and should be in their local zone.

**How to apply:** In bash, prefer `TZ=America/Los_Angeles date +"%H:%M:%S %Z"` over `date -u`. When parsing UTC timestamps from tool output into a human summary, convert: `python3 -c "from datetime import datetime, timezone; from zoneinfo import ZoneInfo; print(datetime.fromisoformat('<utc-iso>').astimezone(ZoneInfo('America/Los_Angeles')).strftime('%H:%M:%S %Z'))"`. For ongoing monitor loops (background polls), set `TZ=America/Los_Angeles` in the loop's date calls so the live progress log is already in local time.
