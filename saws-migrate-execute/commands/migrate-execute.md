---
description: Execute a Track 2 (AI-only → Amazon Bedrock) migration plan and deliver a ready-to-merge git branch.
argument-hint: "[path-to-track2-plan]  (optional — omit to pick interactively)"
---

Invoke the `migrate-execute` skill to execute a Track 2 migration plan.

The plan path is OPTIONAL. If the user provided one, it is here: $ARGUMENTS — use it.
If `$ARGUMENTS` is empty, do NOT error: follow the skill's Step 0 to discover candidate plans under
`./.migration` and `~/saws-migrate-results`, then ask the user which plan to execute via AskUserQuestion
(with a free-text option to paste any directory or .zip path).

Then follow the skill exactly: readiness + Bedrock preflight, then the two-run workflow split by the
post-Eval checkpoint (quality go/no-go + behavior-delta gates), then render the report.
