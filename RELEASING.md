# Release Process

Steps to cut a new DocRawl release. Every release follows this 7-step process.

## Prerequisites

- [ ] All milestone checklist items merged to `main`
- [ ] CI green on `main` (all 14 workflows passing)
- [ ] `pip-audit -r requirements.txt` shows no HIGH/CRITICAL CVEs
- [ ] `python3 scripts/check_doc_freshness.py` prints `OK`
- [ ] Local smoke test passes: `docker compose up -d` + job against httpx docs completes

---

## Step 1: Bump API_VERSION

Edit `src/main.py`:
```python
API_VERSION = "X.Y.Z"
```

## Step 2: Update docs

```bash
# Update PROJECT_STATUS.md header
# Change: > DocRawl v0.X.Y -- Last updated: YYYY-MM-DD
# To:     > DocRawl vX.Y.Z -- Last updated: <today>

# Verify freshness check passes
python3 scripts/check_doc_freshness.py  # must print OK
```

## Step 3: Update CHANGELOG.md

Ensure `## [vX.Y.Z] - unreleased` exists with all PRs for this milestone.
The `update-docs-on-merge.yml` workflow maintains CHANGELOG automatically for each PR.

## Step 4: Commit and open release PR

```bash
git add src/main.py docs/PROJECT_STATUS.md CHANGELOG.md
git commit -m "chore: bump version to vX.Y.Z"
# Open PR titled "release: vX.Y.Z" and assign to the vX.Y.Z milestone
```

## Step 5: Merge the PR

When merged to `main`:
- `update-docs-on-merge.yml` fires → updates README badge, CHANGELOG, pushes `vX.Y.Z` tag

## Step 6: Close the milestone

On GitHub → Milestones → close the `vX.Y.Z` milestone.
`auto-tag.yml` verifies the tag exists (or pushes it if missing).

## Step 7: Verify the release artifacts

- [ ] GitHub Release created by `release.yml` with CHANGELOG body
- [ ] `release.yml` set `is_prerelease=false` for stable semver tags
- [ ] Docker image published to GHCR by `docker-publish.yml`:
  - `ghcr.io/plater7/docrawl:vX.Y.Z`
  - `ghcr.io/plater7/docrawl:latest`
- [ ] Pull and run the published image: `docker run --rm ghcr.io/plater7/docrawl:vX.Y.Z`

---

## Pre-release (alpha/beta/RC) Tags

Use suffixes: `v1.0.0-rc1`, `v1.0.0-beta1`.
`auto-tag.yml` handles these correctly.
`release.yml` marks releases with `alpha`, `beta`, or `rc` in the tag as pre-releases.

---

## Hotfix Process

For urgent fixes on an already-released version:
1. Branch from the tag: `git checkout -b hotfix/vX.Y.Z+1 vX.Y.Z`
2. Apply fix, bump patch version, follow steps 1–7 above
3. PR to `main` only (do not create a long-lived release branch)
