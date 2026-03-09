# UI Two-Column Layout

**Status**: Implemented (PR #153, merged)  
**Refinement**: PR #156 (open) -- 65/35 grid, 1600px max container, sticky right panel

## Overview

The UI uses a two-column layout for better UX, separating configuration from execution monitoring:

```
+------------------+------------------------+
|   LEFT COLUMN    |    RIGHT COLUMN        |
|   (65% width)    |    (35% width)         |
+------------------+------------------------+
| [Crawl Config]   | [Job History]          |
| - URL Input      | - Recent jobs list     |
| - Provider Select| -   Job ID             |
| - Model Config   | -   Status indicator   |
| - Output Path    | -   Stop Button        |
| - Advanced Opts  | -   Timestamp          |
| - Start Button   | [Execution Log]        |
|                  | - Real-time SSE logs   |
|                  | - Phase indicators     |
+------------------+------------------------+
```

## Left Column: Crawl Configuration

Contains all form fields for job setup:
- URL input
- Provider selection (Ollama / OpenRouter / OpenCode / LM Studio)
- Model configuration (crawl, pipeline, reasoning)
- Output path
- Advanced options (delay, concurrency, depth, robots.txt)
- Start/Cancel buttons

## Right Column: Execution & Monitoring

### Job History Panel (sticky)
- List of recent jobs with:
  - Job ID (short form)
  - Status (running, completed, failed, cancelled, paused)
  - Stop/Abort button for running jobs
  - Pause/Resume for active jobs
  - Timestamp

### Logs Section
- Real-time SSE logs
- Collapsible by phase
- Color-coded (error=red, warning=yellow, info=blue)

## Implementation Details

- **CSS Grid**: Two-column layout using CSS Grid
- **Grid ratio**: 65/35 (left/right) as of PR #156
- **Max width**: 1600px container
- **Sticky panel**: Right column uses `position: sticky` for scroll persistence
- **Job history**: Stored in memory (per-session)
- **Job status**: Polled from `/api/jobs/{id}/status`
- **Stop button**: Calls `/api/jobs/{id}/cancel`
- **Pause/Resume**: Calls `/api/jobs/{id}/pause` and `/api/jobs/{id}/resume`
- **Auto-refresh**: Job list refreshes every 30 seconds
- **Phase events**: `phase_change` SSE event emitted before scraping loop (PR #151)

## History

- **PR #153** (merged): Initial two-column implementation
- **PR #151** (merged): Fix `phase_change` event timing
- **PR #156** (open): Refinement -- 65/35 grid ratio, 1600px max container, sticky right panel
