# Intake Guide — Processing Raw Exports Safely

> How to extract knowledge from Notion exports, CLI logs, and chat histories
> into the curated docs without leaking secrets or noise.

---

## The Rule

**Raw data goes in `docs/raw/` (gitignored). Curated content goes in `docs/*.md` (committed).**

Never copy-paste raw exports directly into committed files. Always process through the sanitization steps below.

---

## Step 1: Drop Raw Files

Place your exports in `docs/raw/`:

```
docs/raw/
├── notion-export-2026-03.zip     # Notion workspace export
├── claude-code-session-137.md    # Claude Code CLI session log
├── opencode-session-chunking.md  # OpenCode CLI session log
├── claude-chat-export.json       # Claude.ai conversation export
└── docker-logs-stripe-test.txt   # Container logs from a test run
```

---

## Step 2: Sanitize — Check for Secrets

Before reading any raw file, scan for secrets. Run this from the repo root:

```bash
# Quick grep for common secret patterns
grep -rn -i \
  -e 'OPENROUTER_API_KEY' \
  -e 'OPENCODE_API_KEY' \
  -e 'API_KEY=' \
  -e 'CLOUDFLARE_TUNNEL_TOKEN' \
  -e 'Bearer ' \
  -e 'sk-' \
  -e 'eyJ' \
  -e 'token=' \
  -e 'password' \
  -e 'secret' \
  docs/raw/
```

If anything shows up with actual values (not just variable names), **do not commit those files**. Extract the knowledge manually, leaving the sensitive values out.

**Common things that leak:**
- API keys in Notion pages where you documented setup steps
- Tunnel tokens in Docker Compose examples you pasted into Notion
- Full CLI output that includes environment variables
- Error messages that contain request headers with auth tokens
- Filesystem paths like `/home/yourname/...` (minor but reveals username)

---

## Step 3: Extract by Source Type

### From Notion Exports

Notion exports are usually Markdown or HTML files organized by page title. Look for:

**Architecture notes** → Extract decisions and rationale → Add to `DECISIONS.md`
**Debugging journals** → Extract root cause + fix + lesson → Add to `LESSONS.md`
**TODO lists / roadmap** → Check what's done vs pending → Update `OPEN-QUESTIONS.md`
**Setup guides** → Check for patterns worth documenting → Add to `PATTERNS.md`
**Meeting notes / brainstorms** → Extract decisions made → Add to `DECISIONS.md`

**Skip:** Draft content that never went anywhere, duplicates of what's in git, personal notes unrelated to the project.

### From Claude Code CLI Logs

Claude Code sessions are typically long transcripts of plan → implement → test cycles. Look for:

**Plans that were executed** → If the plan itself was good, note the approach in `PATTERNS.md`
**Bugs discovered during implementation** → Add to `LESSONS.md`
**Decisions made mid-session** → Add to `DECISIONS.md` (the "why" is often only in the CLI session)
**Test results** → If they revealed site-specific behaviors → Add to `TEST-SITES.md`

**Skip:** Intermediate code that was rewritten, debugging dead ends that didn't lead anywhere, verbose tool output.

### From OpenCode CLI Logs

Similar to Claude Code. Additionally look for:

**Different approaches to the same problem** → If OpenCode solved something differently than Claude Code, note both approaches and which worked better in `LESSONS.md`
**Model-specific behaviors** → If a specific model produced better/worse results for a task, note it

### From Claude.ai Chat Histories (These Conversations)

These chats contain the highest-level strategic thinking. Look for:

**Research sessions** → The 764-line analysis document from the tooling research is a goldmine. Key findings should be in `DECISIONS.md` (what was adopted) and `OPEN-QUESTIONS.md` (what was deferred)
**Debugging discussions** → Root cause analysis is often more detailed in chat than in CLI logs → `LESSONS.md`
**Roadmap planning** → The v0.9.7→v0.9.10 milestone plan → `CHANGELOG-NARRATIVE.md`

---

## Step 4: Write the Curated Entry

Follow the format of existing entries in each document. Key rules:

**Be specific:** "LLM cleanup timed out" is useless. "qwen3:14b cleanup hit 367s timeout due to 3×120s retries with backoff" is useful.

**Include the source:** Note when/where the knowledge came from (date, session, site) so you can trace back if needed.

**Include the "why":** Decisions without rationale are just facts. The rationale is what prevents someone from undoing the decision without understanding the context.

**Keep it terse:** These docs are for quick reference, not for storytelling. One paragraph per entry is ideal. The narrative changelog is the exception.

---

## Step 5: Clean Up

After extracting everything useful:

```bash
# Delete the raw files — they're gitignored but no reason to keep them
rm -rf docs/raw/*

# Verify nothing leaked
git diff --cached  # check staged files for secrets
git diff           # check unstaged changes
```

---

## Using AI to Help Process

You can ask Claude (here or in Claude Code) to help extract knowledge from raw exports:

```
I have a Claude Code session log from implementing PR #137 (PagePool).
Extract:
- Any debugging insights → format for LESSONS.md
- Any design decisions made → format for DECISIONS.md
- Any test site behaviors discovered → format for TEST-SITES.md

IMPORTANT: Do NOT include any API keys, tokens, passwords, or filesystem paths
that reveal personal information. Replace with [REDACTED] if quoting.

Here's the log:
[paste log]
```

The key instruction is telling the AI explicitly to redact sensitive content. Don't rely on it noticing automatically.
