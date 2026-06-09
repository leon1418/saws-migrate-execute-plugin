---
name: execution-readiness
description: Plan review and execution readiness gate — reads plan files, dynamically generates deduped questions, displays confirmation summary before execution begins
---

# Execution Readiness Gate

You have just downloaded a migration plan. Before launching any execution phases, you MUST complete this readiness gate. The user must explicitly confirm "Start Migration" before you proceed.

## Step 1: Read Plan Data

List the plan directory and read the files that are present. Do not hardcode any
specific filename — different plan packages may ship different artifacts. Use
the `bash` tool:

```bash
ls -la <plan_directory>
```

For each file you find, decide whether it is plan data (e.g. a Markdown plan
document, a manifest, a runbook, a guide) and `cat` the ones that are. Skip
binaries (`.pdf`, `.zip`) and noise (`.DS_Store`).

From whatever you read, extract and remember (any field may be missing — do not
fabricate values):

- The migration **track** (Track 1 — Infrastructure, or Track 2 — AI-Only)
- The list of **service mappings** (source resource → target AWS service)
- Any **risks** the plan flagged, with severity if available
- The plan's **overall confidence** if stated
- The **estimated AWS monthly cost** if stated
- The plan's **age** (creation timestamp) if available

If a section is absent from the plan, simply note it as unknown and move on.

## Step 2: Classify Plan Confidence

**High-confidence plan (max 3 readiness questions):**
- Plan is less than 30 days old
- The plan does not flag any HIGH-severity risks
- The plan's stated overall confidence is "High"

**Low-confidence plan (5-7 readiness questions):**
Any of the above conditions fails, or the relevant data is unavailable.

## Step 3: Generate Dynamic Readiness Questions

Review the plan data and ask only the questions below that are not already
answered by the plan content itself.

### Gap Categories (in priority order)

1. **HIGH-severity risks acknowledged**: For each HIGH-severity risk the plan
   lists, ask the user to confirm they have reviewed it and accepted the
   mitigation. Example: "The plan flagged a HIGH risk: data loss during
   GCS→S3 migration if versioning is not enabled. Have you reviewed and
   accepted the mitigation?"

2. **Stale plan**: If the plan's creation date is older than 30 days, ask
   whether the user has re-validated the plan. Example: "This plan was
   generated 45 days ago. AWS pricing or your source environment may have
   changed. Proceed with this plan, or regenerate?"

3. **Missing operational context** — Ask unless the plan explicitly answers
   it (rare for these — they're runtime context the plan typically does not
   record):
   - Maintenance window preference: "Do you have a preferred maintenance window, or can we migrate anytime?"
   - Concurrent codebase changes: "Is anyone else actively pushing changes to this codebase right now?"
   - Third-party API test keys: If the plan references external APIs (Stripe, Twilio, etc.), ask: "Do you have sandbox/test credentials for [service]?"
   - DNS/domain readiness: "Is the domain [domain] ready for DNS cutover, or will that happen separately?"

4. **Resource naming conflicts**: If the plan targets a specific AWS region or account, ask: "Are there existing AWS resources in [region] that might conflict with this migration?"

### Deduplication Rules

- If the answer to a category is already in the plan content, SKIP it
- NEVER re-ask a question the plan already answers
- You MUST NOT exceed the maximum question count (3 for high-confidence, 7 for low-confidence)
- If you have more potential questions than the max, prioritize by impact on execution success

## Step 4: Ask Questions One at a Time

For each question you decide to ask:

1. Use the `question` tool with a SINGLE question
2. Provide relevant multiple-choice options plus free-text (custom is enabled by default)
3. After the user answers, compare the answer against the plan data
4. **If conflict detected**: Immediately ask a follow-up conflict resolution question:
   ```
   question: "The migration plan says [X], but you indicated [Y]. Which should we use for execution?"
   options:
     - label: "Use the plan value: [X]"
       description: "Keep what was decided during planning"
     - label: "Use my answer: [Y]"
       description: "Override the plan with your current preference"
   ```
5. Record any user overrides (answer differs from plan)

Track:
- Questions asked (count)
- User overrides (list of {field, plan_value, user_value})

## Step 5: Display "Ready to Execute" Summary

After all questions are answered (or if none were needed), present the summary via the `question` tool.

### Summary Display

Construct the summary from the plan data you read in Step 1. Omit any line whose
underlying field is not available in the plan — do not fabricate placeholders.

```
question: "Ready to execute this migration?"
header: "Ready to Execute"
options:
  - label: "Start Migration (Recommended)"
    description: "Proceed to sandbox provisioning and execution"
  - label: "Review Plan Again"
    description: "Go back and review the plan files before starting"
```

In the question text, include this information (omit lines whose data is unavailable):

```
Ready to Execute:
  Track: [Track 1 — Infrastructure | Track 2 — AI-Only]
  Services: [list each mapping, e.g. "Cloud SQL → Aurora, GCS → S3"]
  Estimated AWS cost: ~$[monthly]/month (your app's ongoing AWS spend)
  Plan confidence: [High | Medium | Low]   (omit if not in plan)
  HIGH risks accepted: [count]             (omit if no HIGH risks)
  [If overrides exist:]
  Overrides from review:
    - [override 1]
    - [override 2]
```

Keep the question text SHORT — under 15 lines. The question tool displays in a small panel.

**Track 2 (AI-Only) only — append this note to the summary text:**

```
Note: this readiness gate runs BEFORE source code analysis, so the exact
count of behavior differences is not yet known. Known differences between
[source_provider] and Bedrock include temperature range, response_format /
JSON mode, presence/frequency penalties, and (for Gemini) candidate_count
and safety_settings. The code analysis phase will enumerate the ones that
actually appear in your code, and the rewrite phase will ask you to confirm
each user-visible change before modifying code.
```

Skip this note for Track 1 and for Track 2 when the plan indicates the source
provider stays in the same model family (e.g. Anthropic 1P → Bedrock).

**If user selects "Review Plan Again":** Tell the user they can browse the plan files in the sidebar, then re-display the summary when they're ready.

**If user selects "Start Migration":** Proceed to the next step.

## Step 6: Output

After the user confirms "Start Migration", record the readiness outcome.

Summarize the readiness gate's outcome (the `ReadinessData` fields below) and carry it forward into the migration run, so later phases have the context the gate produced.

Record these fields:

- `plan_confidence` — the confidence classification from Step 2 (`high` | `medium` | `low`).
- `questions_asked` — how many readiness questions you asked the user.
- `service_count` — the number of service mappings you extracted from the plan in Step 1.
- `user_overrides` — the list of overrides recorded in Step 4 (answers that differed from the plan), e.g. `aws_region: plan said us-west-2, user chose us-east-1`. If there are no overrides, this is an empty list.

Also keep a short prose summary of the outcome, e.g. "Plan reviewed; 4 services mapped; estimated AWS cost ~$120/mo. Ready to start."
