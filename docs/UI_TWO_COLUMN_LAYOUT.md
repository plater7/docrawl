# UI Two-Column Layout - Future Redesign

**Status**: TODO / Planning
**Target**: Future PR

## Overview

Redesign the UI into two columns for better UX:

```
+------------------+------------------------+
|   LEFT COLUMN    |    RIGHT COLUMN        |
+------------------+------------------------+
| [Current Form]   | [Job Control]          |
| - URL Input      | - Execute Button       |
| - Provider Select| - Status Banner        |
| - Model Config   | - Progress Logs         |
| - Output Path   | - Job History Panel    |
| - Advanced Opts |   - Job ID              |
| - Start Button  |   - Status (running/done)|
|                  |   - Stop Button         |
+------------------+------------------------+
```

## Left Column: Crawl Configuration

Keep existing form fields:
- URL input
- Provider selection (Ollama/OpenRouter/OpenCode)
- Model configuration (crawl, pipeline, reasoning)
- Output path
- Advanced options (delay, concurrency, depth, robots.txt)
- Start/Cancel buttons

## Right Column: Execution & Monitoring

### Job Control Section
- **Execute Button**: Start crawl with current config
- **Status Banner**: Shows current phase (init, discovery, filtering, scraping, cleanup, done)
- **Progress**: Current URL being processed, pages completed/total

### Job History Panel
- List of recent jobs with:
  - Job ID (short form)
  - Status (running, completed, failed, cancelled)
  - Stop/Abort button for running jobs
  - Timestamp

### Logs Section
- Real-time SSE logs
- Collapsible by phase
- Color-coded (error= red, warning= yellow, info= blue)

## Implementation Notes

- Use CSS Grid for two-column layout
- Job history stored in memory (per-session) or localStorage
- Job status from `/api/jobs/{id}/status`
- Stop button calls `/api/jobs/{id}/cancel`
- Auto-refresh job list every 30 seconds
