# Manual Validation — Track 2 Execute Plugin (live Bedrock)

Prereqs: a real Track 2 plan, a sample Gemini/OpenAI repo, AWS creds with Bedrock access, `uv`.

1. Install the plugin locally (point Claude Code at `plugin/saws-migrate-execute/`).
2. Run `/migrate-execute <plan-path>`.
3. **Readiness:** confirm the readiness questions appear and the "Ready to Execute" summary renders.
4. **Preflight:** with creds that LACK `bedrock:InvokeModel`, confirm it fails fast with the IAM action named — NOT mid-eval. Then fix creds and re-run.
5. **Region:** point at a region without the target model; confirm the cross-region inference profile is suggested.
6. **Run 1:** confirm Analyze→Ingest→Eval progress in `/workflows`; confirm structured results return.
7. **Throttle:** (optional, new-account) confirm a 429 during Eval triggers backoff, not a crash; if budget exhausts, confirm the `partial` prompt offers continue/proceed/abort.
8. **Gate (a):** force a low pass rate (e.g. wrong model); confirm proceed/change-model/abort appears and "change model" re-runs Eval. Confirm the 2-retry cap.
9. **Gate (b):** use a repo with an OpenAI `temperature=2` slider; confirm the behavior-delta prompt appears and the choice is honored (no silent capping).
10. **Run 2:** confirm a `bedrock-migration` branch is created in an isolated worktree (user's working tree stays clean), tests run, and `MIGRATION_REPORT_<date>.md` is written.
11. **Render:** confirm the in-chat summary + verbatim report, and the archived copy under `~/saws-migrate-results/`.

Record pass/fail per step. All must pass before publishing.
