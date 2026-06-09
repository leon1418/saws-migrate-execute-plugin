---
name: migrate-execute
description: Execute an AI-only (Gemini/OpenAI → Amazon Bedrock) migration plan. Triggers on /migrate-execute (the plan path is optional — if omitted, the skill discovers candidate plans and asks). Runs readiness + Bedrock preflight, then a two-run workflow split by one post-Eval checkpoint, delivering a ready-to-merge bedrock-migration branch.
---

# Migrate Execute (Track 2 — AI-only → Bedrock)

Executes an EXISTING Track 2 plan. Does not generate plans.

The skill base directory is given in the "Base directory for this skill: X" line the harness
emits at load time. Call it `<SKILL_BASE>`. The plugin scripts are at `<SKILL_BASE>/../../scripts`
and agents at `<SKILL_BASE>/../../agents`.

## Step 0 — Obtain the plan path

The plan path is OPTIONAL on the command line. Resolve it as follows:

1. **If `$ARGUMENTS` contains a path**, use it as the plan path (skip to Step 1). If that path doesn't
   exist, treat it as "no path given" and continue with discovery below.

2. **Otherwise, discover candidate plans, then ask the user with AskUserQuestion.** Do NOT print a usage
   error and stop — always ask. Build the candidate list by scanning the two conventional locations for
   directories that look like a Track 2 plan (have a `metadata.json` with `scope == "AI_ONLY"`, OR a
   `MIGRATION_PLAN.md`):

   ```bash
   # Find .migration — may be in CWD, a parent, or at the git root. Walk up to find it.
   MIGRATION_DIR=""
   d="$(pwd)"
   while [ "$d" != "/" ]; do
     if [ -d "$d/.migration" ]; then MIGRATION_DIR="$d/.migration"; break; fi
     d="$(dirname "$d")"
   done
   # Scan found .migration + the planning skill's archive dir; print "<scope>\t<dir>"
   for base in ${MIGRATION_DIR:+"$MIGRATION_DIR"} "$HOME/saws-migrate-results"; do
     [ -d "$base" ] || continue
     for dir in "$base"/*/; do
       [ -d "$dir" ] || continue
       scope=$(node -e "try{process.stdout.write(String(JSON.parse(require('fs').readFileSync('$dir/metadata.json')).scope||''))}catch(e){}" 2>/dev/null)
       if [ "$scope" = "AI_ONLY" ] || [ -f "$dir/MIGRATION_PLAN.md" ]; then printf '%s\t%s\n' "${scope:-?}" "$dir"; fi
     done
   done
   ```

   Prefer `AI_ONLY` candidates (this is a Track 2 plugin). Present the AI_ONLY directories first
   (most-recent first, up to 4) as AskUserQuestion options, each labeled with the directory name. If the
   only candidates found are non-AI_ONLY (e.g. `FULL`/`INFRA_ONLY` — Track 1), still list them but mark
   the label "(Track 1 — not supported)" so the user understands; selecting one will be rejected at
   Step 1. AskUserQuestion always offers a free-text "Other" choice, so the user can paste any path (a
   directory **or** a `.zip`) you didn't list. Phrase the question: "Which migration plan should I
   execute? (pick one, or choose Other to enter a path)".

   - If discovery finds candidates, list them.
   - If discovery finds none, still ask the question with no preset options beyond the implicit "Other"
     free-text — prompt: "I didn't find a plan under ./.migration or ~/saws-migrate-results. Enter the
     path to your Track 2 plan (directory or .zip). No plan yet? Generate one with the `saws-migrate`
     planning skill, then re-run this."

3. Use the user's selected/entered path as the plan path. This skill executes an EXISTING plan — it does
   NOT generate one. If the user has no plan, point them to the `saws-migrate` planning skill and stop.

## Step 1 — Import & detect track

If the path is a `.zip`, unzip to a temp dir and treat the unzipped directory as the plan dir.

Detect the track from the plan's actual contents (do NOT look for `.phase-status.json` or an
`ai-migration/` directory — those do not exist; the planning-side `saws-migrate` skill does not
produce them). The real Track 2 plan directory contains:
- `metadata.json` — read it; **`scope == "AI_ONLY"` means Track 2.** (There is no `track` field.)
- `MIGRATION_PLAN.md` — human-readable plan (architecture, considerations, resource-mapping table, risks).
- `AI_MIGRATION_GUIDE.md` — contains the **Model Mapping** table (source model → target Bedrock model
  with real model IDs like `anthropic.claude-haiku-4-5-20251001-v1:0`) and SDK-migration samples.
- `MIGRATION_PLAN.pdf` — binary copy; ignore.

Detection logic (in order):
1. If `metadata.json` exists and its `scope == "AI_ONLY"` → Track 2. Proceed.
2. Else if `metadata.json` has `scope` containing `INFRA` (e.g. `INFRA_ONLY`/`FULL`), or a `terraform/`
   directory is present → Track 1. Stop: "This plugin handles AI-only (Track 2) plans; this looks like
   an infrastructure plan."
3. Else (no `metadata.json` / no scope): fall back to content — if `AI_MIGRATION_GUIDE.md` or a
   `MIGRATION_PLAN.md` describing an LLM/Bedrock migration is present (and no `terraform/`), treat as
   Track 2. If you truly can't tell, ask the user via **AskUserQuestion** whether this is an AI-only plan.

Record `planDir` (the resolved plan directory) and the target Bedrock model IDs parsed from the
`AI_MIGRATION_GUIDE.md` Model Mapping table — Step 4's preflight and the workflows need them.

## Step 2 — Readiness

Load the `execution-readiness` skill. Follow it: read plan files, classify confidence, ask the
dynamic readiness questions via **AskUserQuestion**, show the "Ready to Execute" summary.

## Step 3 — Collect inputs (AskUserQuestion)

Collect three things from the user. Use AskUserQuestion for each (or combine where natural).

### 3a. Source code location

Local path (default) or GitHub URL. If a URL, `git clone` it to a temp dir; use that path as `repo`.

**After obtaining the repo path, run two checks before proceeding:**

1. **Git-root check.** The repo MUST be at its own git root (not nested inside another repository's
   gitignored directory — that causes the rewriter to place files in a subdirectory). Run:
   ```bash
   git -C <repo> rev-parse --show-toplevel
   ```
   If the output differs from `<repo>` (i.e. the git root is a PARENT directory), warn the user:
   "This path is inside a larger git repository at <root>. The rewriter needs the source at its own
   git root. Either `cd` there, or copy the project to a standalone location." Stop and re-ask.

2. **Dirty-tree check.** Run:
   ```bash
   git -C <repo> status --porcelain
   ```
   If there are uncommitted changes (deleted files, modifications, untracked files beyond `.DS_Store`),
   show the status to the user and AskUserQuestion: "The source repo has uncommitted changes (shown
   above). These may interfere with the migration branch. Options:"
   - **Continue anyway** (the rewriter will work on top of the current state)
   - **Let me clean it up first** → stop; user fixes and re-runs

### 3b. AWS credentials confirmation

The plugin uses the user's LOCAL AWS credentials (from `aws configure` / credential helper /
environment variables). Before proceeding, **show the user what identity will be used and ask for
confirmation**. Run:

```bash
aws sts get-caller-identity 2>&1
```

Then present the result to the user via AskUserQuestion:
- Show the Account, Arn, and UserId from the output.
- Ask: "This is the AWS identity that will be used for Bedrock calls. Is this correct?"
- Options:
  - **Yes, use this identity** (proceed)
  - **Use a different AWS profile** → ask the user which profile name to use (from `~/.aws/config`),
    then set `AWS_PROFILE=<their choice>` in the environment for all subsequent commands and re-run
    `aws sts get-caller-identity` to confirm.
  - **Enter credentials manually** → ask for access key / secret key / session token (or just a
    profile name), set them, and re-confirm.

Also collect the **AWS region** for Bedrock (default from their env or ask). Show what region was
detected and let them override.

### 3c. Source-provider API key (optional)

Enables live source-model baseline in Eval. If the user declines, Eval uses a static/synthetic
baseline and the report banners the gap. Never echo the key; write it to a mode-600 env file and
pass only a reference (`sourceKeyRef`).

**IMPORTANT:** Do NOT use AskUserQuestion's free-text "Other" box for the API key — that would
expose it in the transcript. Instead, provide a shell command the user can run in their terminal:

```
! read -sp "Paste your source-provider API key: " KEY && printf "%s" "$KEY" > <repo>/.saws-migrate/.source-provider-env && chmod 600 <repo>/.saws-migrate/.source-provider-env && echo " ✓ key saved"
```

Then offer two AskUserQuestion options:
- **Key saved — continue with live baseline**
- **Skip — proceed without live baseline**

Record the user's choice as a boolean `sourceBaselineAvailable`:
- "Key saved" → `sourceBaselineAvailable = true`, `sourceKeyRef = "<repo>/.saws-migrate/.source-provider-env"`
- "Skip" → `sourceBaselineAvailable = false`, `sourceKeyRef = ""`

These are passed to the workflow in Step 5 so the evaluator knows whether to run the live baseline.

## Step 4 — Bedrock fail-fast preflight

Run: `uv run --project <SKILL_BASE>/../../scripts python <SKILL_BASE>/../../scripts/preflight_bedrock.py --region <region> --models <target Bedrock model IDs from the AI_MIGRATION_GUIDE.md Model Mapping table, comma-separated> --dataset-size <golden cases if known>`
Parse the JSON. If `ok == false`:
- `reason: authz` → tell the user the exact IAM action to grant; stop.
- `reason: model_unavailable` → load `resolve-bedrock-model-id`; offer the cross-region inference profile id; stop or re-collect.
Surface any `quota_warning` to set expectations. If `uv`/`python3` is missing, stop with the install line: `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Step 5 — Confirm & dispatch run 1

After the user selects "Start Migration", call `Workflow` with `scriptPath = <SKILL_BASE>/workflow-analyze.js` and `args`:
```json
{
  "skillBase": "<SKILL_BASE>",
  "repo": "<repo path>",
  "region": "<AWS region>",
  "planDir": "<plan directory>",
  "targetModels": ["<model-id-1>", ...],
  "logFiles": [],
  "sourceBaselineAvailable": true/false,
  "sourceKeyRef": "<repo>/.saws-migrate/.source-provider-env" or "",
  "resolution": {}
}
```
`sourceBaselineAvailable` and `sourceKeyRef` come from Step 3c — they tell the evaluator whether to
run the live source-model baseline. The workflow passes them through to the evaluator's context.

The workflow runs in the background; tell the user the task id and that a notification arrives on completion.

## Step 6 — Handle run-1 result

On completion, read the returned object:
- `control: 'blocked'` → use AskUserQuestion to resolve (enable model / new key / pick model id). Set the typed `args.resolution` field (`resolvedModelId` / `sourceKeyRef`), then re-invoke the SAME workflow with `resumeFromRunId` set to the run id. (Changing a resolution key re-runs only the affected phase and later — the cache rule is enforced by the phase prompt builders.)
- `control: 'partial'` (throttled Eval) → AskUserQuestion: continue remaining cases (resume), proceed to the checkpoint with the partial pass rate (labeled partial), or abort.
- `control: 'ok'` → go to Step 7.

## Step 7 — Checkpoint (two gates)

**Gate (a) — Quality go/no-go.** Show the eval summary verbatim (pass rate, per-prompt scores, baseline-mode banner, partial banner if any). If below the plan's threshold, OR Eval was partial, OR `evalRes.source_baseline_quality == 'poor'`, AskUserQuestion:
- **Proceed anyway** → gate (b).
- **Change target model** → pick a different Bedrock model; re-invoke run 1 via `resumeFromRunId` with `args.resolution.resolvedModelId` set (re-runs Eval and the phases that consume the model id). **Cap: 2 model-change retries**; after that only proceed-with-risk or abort remain.
- **Abort** → stop; no code touched.

**Gate (b) — Behavior-delta resolution.** For each `analysis.behavior_deltas[]` where `user_visible == true`, AskUserQuestion with the options from `behavior-delta-detection` (cap to target range / linear rescale / keep + warn). Collect into `deltaDecisions[]`.

## Step 8 — Dispatch run 2

Call `Workflow` with `scriptPath = <SKILL_BASE>/workflow-rewrite.js` and `args = { skillBase, repo, region, planDir, targetModels, resolution, analysis, ingest, evalRes, deltaDecisions, reportDateSuffix: <YYYY-MM-DD you compute now via Bash date> }`.

## Step 9 — Render

On completion, write the run-2 result JSON to a temp file, then run `uv run --project <SKILL_BASE>/../../scripts python <SKILL_BASE>/render_report.py <tmp.json>`. Print its summary. Re-emit the full report (`report.report_path`) verbatim in chat. Point the user at the `bedrock-migration` branch.

## Failure handling

- Workflow throws → show the error; don't auto-retry.
- User aborts at a gate → confirm nothing was modified (run 2 never started).
