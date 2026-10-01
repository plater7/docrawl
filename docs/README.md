# DocRawl — Project Knowledge Base

> Living documentation. Single source of truth for anyone (human or AI) working on the project.
> Last reviewed: 2026-03-07

## Structure

| Document | Purpose | When to read |
|----------|---------|-------------|
| [DECISIONS.md](DECISIONS.md) | Architecture choices and rationale | Before proposing changes |
| [LESSONS.md](LESSONS.md) | Bugs, pitfalls, hard-won knowledge | Before implementing anything |
| [PATTERNS.md](PATTERNS.md) | Conventions and patterns that work | When writing new code |
| [CHANGELOG-NARRATIVE.md](CHANGELOG-NARRATIVE.md) | Project story from v0 to now | For onboarding / context |
| [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) | Unresolved decisions and gaps | For planning sessions |
| [TEST-SITES.md](TEST-SITES.md) | Doc sites used for testing + known behaviors | Before integration tests |
| [INTAKE-GUIDE.md](INTAKE-GUIDE.md) | How to safely process raw exports into these docs | When consolidating new data |
| [SSE-EVENTS.md](SSE-EVENTS.md) | Server-Sent Events schema and behavior | When building SSE client or debugging streaming |

## Usage with AI agents

Add this to your Claude Code / OpenCode prompt or CLAUDE.md:

```
Before starting work, read these files for project context:
- SNAPSHOT.md (auto-generated current code state)
- docs/DECISIONS.md (why things are the way they are)
- docs/LESSONS.md (what NOT to do — saves you from repeating mistakes)
- docs/PATTERNS.md (conventions to follow)
- docs/OPEN-QUESTIONS.md (what's still unresolved)
```

## Maintenance rules

- **Debugged a hard bug?** → Add to LESSONS.md
- **Made a design choice?** → Add to DECISIONS.md
- **Found a test site quirk?** → Add to TEST-SITES.md
- **Merged a milestone PR?** → Update CHANGELOG-NARRATIVE.md
- **Deferred something?** → Add to OPEN-QUESTIONS.md
- **Processing raw exports?** → Follow INTAKE-GUIDE.md
