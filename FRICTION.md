# Friction Log

Developer-experience friction encountered building Rein. Each entry:
task attempted, steps taken, expected vs actual, severity, workaround,
and an actionable suggestion.

Severity: **Blocker** (cannot proceed) · **Major** (hours lost) ·
**Minor** (annoyance) · **Papercut** (trivial but repeated)

---

## F-001 — Alexa+ MCP Toolkit is unreachable, and the sanctioned alternative is undocumented

- **Date:** 2026-09-18
- **Severity:** Blocker (for the documented path); resolved by an
  undocumented alternative
- **Component:** Alexa+ Developer Console · Alexa+ Builder Docs · hackathon rules

**Task attempted.** Register an Alexa+ MCP add-on in order to develop
and test an MCP server against Alexa+, as the Alexa+ track requires.

**Steps.**

1. Signed in to the Amazon Developer Console with a registered hackathon
   account.
2. Opened Alexa+ → Alexa+ Developer Console. Listed as unavailable.
3. Opened the Alexa+ Builder Docs. Banner: _"At this time, Category SDK
   and MCP Toolkit are available to select partners only."_
4. Searched the hackathon Discord. Another participant had hit the same
   wall on 2026-09-09 and published an Alexa-Skill-to-MCP bridge as a
   workaround.
5. Asked directly in `#amazon-developer-general-chat`.

**Expected.** A hackathon whose primary track is Alexa+ MCP add-ons
would grant registered participants access to the MCP add-on tooling, or
state prominently in the rules that it does not.

**Actual.** Access is partner-only and was confirmed as not available to
participants for the duration. The acceptable alternatives — a
self-hosted MCP server on the open standard, a working Agent Skill, or a
simulated Alexa+ experience using one's own agentic tools — were
confirmed only in response to a direct Discord question, not in the
track rules or the developer documentation.

**Impact.** Roughly one day of schedule risk carried as an unresolved
unknown, and a strategy that could not be finalised until it was
answered. Participants who do not think to ask in Discord may assume the
track is closed to them, or may build toward tooling they will never
receive.

**Workaround.** Build the MCP server to the open specification
(2025-11-25) and drive it with a self-built client. The server is
portable to a real Alexa+ host unchanged.

**Suggested fix, in priority order.**

1. State the three acceptable integration paths in the Alexa+ track
   rules on the submission page — the first place a participant looks.
2. Replace the console's "Coming Soon" with an explanatory note: what it
   is, who can access it, and what a hackathon participant should do
   instead.
3. Add a banner to the Alexa+ Builder Docs landing page linking
   participants to the self-hosted path.
4. Consider a time-boxed sandbox tier for registered participants.

**Feature request.** An offline or local Alexa+ MCP simulator —
equivalent to the ASK local debugger — that validates add-on behaviour
without partner access. **Priority: Critical** for any future hackathon
built on this tooling.

---

## F-002 — Implementation guide's Part ordering broke `uv sync`

- **Date:** 2026-09-19
- **Severity:** Major
- **Component:** Phase 1 implementation guide (AI-authored)

**Task attempted.** Follow the guide's Parts 1→2→3 sequentially, then run
`uv sync --all-extras --group dev` (Part 3.3).

**Expected.** Environment syncs successfully.

**Actual.** Build failure: `OSError: Readme file does not exist:
README.md`. Part 3.2's `pyproject.toml` declares `readme = "README.md"`,
which hatchling validates before building — but the guide didn't create
`README.md` until Part 6, several parts later.

**Impact.** Blocked at the first `uv sync` call with no way to recover
except inferring the correct order independently.

**Workaround.** Create Part 6's documentation files before running Part
3.3. Documented as the corrected sequence in `Rein_Blueprint.md` §23.

**Suggested fix.** Any AI-authored implementation guide needs a
dependency matrix checked *before* the parts are numbered, not
discovered by the person following it.

---

## F-003 — Quality-gate config file created in the wrong directory

- **Date:** 2026-09-27
- **Severity:** Minor
- **Component:** Phase 1 implementation guide (AI-authored)

**Task attempted.** Follow Part 4.2 to create `.pre-commit-config.yaml`
at the repo root.

**Actual.** The file was created at `scripts/.pre-commit-config.yaml`
instead. `pre-commit` only discovers this file at the repository root by
convention, so `uv run pre-commit install` would have silently installed
hooks that never actually ran any checks — the failure mode is *quiet*,
not an error message, which makes it worse than F-002.

**Impact.** Caught only by manually auditing repo state before pushing;
would otherwise have shipped a CI/local hook setup that looked configured
but did nothing.

**Workaround.** `Move-Item scripts\.pre-commit-config.yaml .pre-commit-config.yaml`

**Suggested fix.** Guides that create config files with strict location
requirements (pre-commit, ESLint, editorconfig, etc.) should state the
required path explicitly and a verification step ("confirm it's at the
repo root, not a subfolder") rather than relying on the reader to infer
convention.

---

## F-004 — Action-SHA resolver script omitted an action actually used in CI

- **Date:** 2026-09-27
- **Severity:** Minor
- **Component:** `scripts/resolve-action-shas.ps1` (AI-authored)

**Task attempted.** Run `resolve-action-shas.ps1` to get immutable commit
SHAs for every third-party GitHub Action referenced in
`.github/workflows/*.yml`, per the supply-chain hardening step (Part
5.1).

**Expected.** The script resolves a SHA for every `uses:` line across all
workflow files.

**Actual.** The script's hardcoded `$actions` list included
`actions/checkout`, `astral-sh/setup-uv`, and `github/codeql-action`, but
**not** `gitleaks/gitleaks-action` — even though `ci.yml`'s `secrets` job
uses it. The gap was invisible until manually cross-checking every
`uses:` line in the workflow files against the script's list.

**Impact.** Would have shipped a workflow with one action still pinned to
a mutable tag (`@<SHA>` literally unreplaced), defeating the supply-chain
hardening for that one action while looking complete everywhere else.

**Workaround.** Resolved manually:
`gh api "repos/gitleaks/gitleaks-action/commits/v2" --jq '.sha'`

**Suggested fix — implemented.** Added a self-check to the script that
greps every `.github/workflows/*.yml` file for `uses:` lines and warns if
any referenced repo isn't in the `$actions` list, so the gap surfaces
automatically instead of requiring a manual audit.

---

## F-005 — Windows long-path limit breaks dependency installs
