---
name: write-technical-requirements
description: Write or refine technical requirements for this repo, including feature scope, workflow, acceptance criteria, and UI/API/database impacts. Use when creating or updating markdown requirements in `requirements/` before implementation or review.
---

# Write Technical Requirements

## Goal

- Produce implementation-ready markdown requirements that match the style already used in `requirements/`.
- Make scope, contracts, and workflow concrete enough that UI, API, and database work can be estimated and reviewed.

## Document Type

- Use `# Epic:` for broader multi-feature work.
- Use `# Feature:` for a single workflow or capability.
- Keep titles short and action-oriented.

## Standard Sections

- Summary or Description
- In Scope and Out of Scope when the work is broad enough to need boundaries
- User Stories when actor goals matter
- Acceptance Criteria
- Workflow
- API Specs
- UI Specs
- Database Specs

## Writing Rules

- Match the concise repo pattern used in `requirements/*.md`.
- Prefer specific nouns and endpoint names over generic intent language.
- Write acceptance criteria as observable outcomes, not implementation steps.
- Separate current state assumptions from required changes.
- If the feature touches an external integration, add the failure, retry, and data ownership expectations in the relevant section.

## Cross-Layer Alignment Checklist

- Name the frontend surface correctly: `web/` React or `ui/` Streamlit.
- Keep endpoint names and payload fields aligned with likely schema names.
- Note when a database change implies a migration or backfill.
- Call out when caching, notifications, background jobs, or scheduled scripts are part of the flow.

## When Architecture Detail Is Needed

- Add a short `## Technical Notes` or `## Rollout Notes` section only when the change has material sequencing or compatibility risk.
- Use that section for migration order, contract versioning, or integration safeguards.

## Related Skills

- Use `$feature-contracts-specs` when the requirements need exact request and response shapes.
- Use `$senior-software-engineer-agent` when the task needs architecture tradeoffs, phasing, or cross-layer planning in addition to document writing.
- Use `$ux-requirements` when the task is primarily UX-facing rather than engineering-facing.
