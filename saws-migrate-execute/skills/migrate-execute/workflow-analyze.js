export const meta = {
  name: 'saws-migrate-execute-analyze',
  description: 'Track 2 run 1: analyze local repo, ingest logs into a golden dataset, evaluate against Bedrock. Returns structured analysis/ingest/eval or a blocked/partial control state.',
  phases: [{ title: 'Analyze' }, { title: 'Ingest' }, { title: 'Eval' }],
}

// ===== Schemas (inlined — the Workflow runtime wraps this body in an async fn,
// so static `import` is illegal and there is no node:fs). Ported verbatim from
// the former schemas.js: AI_ANALYSIS, LOG_INGESTION, EVAL, withControlStates. =====
const str = { type: 'string' }
const strArr = { type: 'array', items: { type: 'string' } }
const bool = { type: 'boolean' }
const int = { type: 'integer', minimum: 0 }

const AI_ANALYSIS = {
  type: 'object', additionalProperties: false,
  required: ['source_code_path', 'app_language', 'ai_framework', 'source_provider',
             'source_models', 'target_models', 'same_model_family', 'files_to_modify',
             'behavior_deltas'],
  properties: {
    summary: str,
    source_code_path: str, migration_plan_path: str, app_language: str,
    ai_framework: str, ai_framework_version: str, source_provider: str,
    source_models: strArr, target_models: strArr,
    same_model_family: bool, bedrock_provider_available: bool,
    prompt_locations: strArr, prompt_patterns: str,
    special_patterns: {
      type: 'object', additionalProperties: false,
      properties: { streaming: bool, function_calling: bool, embeddings: bool, vision: bool },
    },
    code_change_sites: int, files_to_modify: strArr, dependencies_to_replace: strArr,
    log_files_found: str, errors: str, source_baseline_available: bool,
    // user-visible parameter-surface diffs the rewriter must confirm (behavior-delta-detection).
    // Field contract MUST match skills/behavior-delta-detection/SKILL.md (the emit/consume source of truth):
    // delta_type, location, source_value, target_constraint, user_visible, resolution_kind, option_set_id.
    // option_set_id is omitted when resolution_kind == "impl_path".
    behavior_deltas: {
      type: 'array', items: {
        type: 'object', additionalProperties: false,
        required: ['delta_type', 'location', 'user_visible', 'resolution_kind'],
        properties: {
          delta_type: str,
          location: str,
          source_value: str,
          target_constraint: str,
          user_visible: bool,
          resolution_kind: { type: 'string', enum: ['ux_choice', 'impl_path'] },
          option_set_id: str,
        },
      },
    },
  },
}

const LOG_INGESTION = {
  type: 'object', additionalProperties: false,
  required: ['golden_dataset_path', 'total_golden_cases', 'coverage_level'],
  properties: {
    summary: str,
    golden_dataset_path: str, prompt_template_path: str, total_golden_cases: int,
    golden_from_logs: int, golden_from_user: int, golden_from_code_confirmed: int,
    vision_test_images: int, log_format: str, coverage_level: str, use_case_type: str,
    gaps: strArr, pii_detected: bool, pii_action: str, errors: str,
  },
}

const EVAL = {
  type: 'object', additionalProperties: false,
  required: ['eval_report_path', 'pass_rate', 'total_cases', 'failures'],
  properties: {
    eval_report_path: str,
    pass_rate: { type: 'number', minimum: 0, maximum: 1 },
    total_cases: int, failures: int, notes: str,
    live_source_baseline: bool, judge_model: str,
    // forwarded signal: the source model itself looked poor (stale key / wrong version)
    source_baseline_quality: { type: 'string', enum: ['good', 'poor', 'unknown'] },
  },
}

// Wrap a base schema so an agent can return a control state INSTEAD of the payload.
// blocked = hard error needing user resolution; partial = throttle-truncated run.
function withControlStates(base) {
  return {
    type: 'object', additionalProperties: false,
    properties: {
      ...base.properties,
      blocked: {
        type: 'object', additionalProperties: false,
        properties: {
          reason: { type: 'string', enum: ['model_access', 'source_key_auth', 'model_unresolvable'] },
          detail: str,
        },
      },
      partial: {
        type: 'object', additionalProperties: false,
        properties: { completed: int, total: int, reason: { type: 'string', enum: ['throttled'] } },
      },
    },
  }
}

// ===== Context block (inlined buildContext from the former prompts.js) =====
// Deterministic (no Date/random) context block injected into every phase prompt.
// The agent's full system prompt comes from its registered plugin subagent (loaded
// via agentType); we pass only context + prior-phase JSON here.
function buildContext(ctx) {
  const lines = [
    `Repository: ${ctx.repo}`,
    `AWS region: ${ctx.region}`,
    `Target Bedrock model(s): ${(ctx.targetModels || []).join(', ')}`,
    ctx.planDir ? `Migration plan dir: ${ctx.planDir}` : null,
    ctx.resolvedModelId ? `Resolved target model id: ${ctx.resolvedModelId}` : null,
    ctx.scriptsDir ? `Scripts directory (pinned uv toolchain): ${ctx.scriptsDir}` : null,
    ctx.reportDateSuffix ? `Report date suffix: ${ctx.reportDateSuffix}` : null,
    `Source baseline available: ${ctx.sourceBaselineAvailable ? 'true' : 'false'}`,
    ctx.sourceKeyRef ? `Source provider env file: ${ctx.sourceKeyRef}` : null,
  ].filter(Boolean)
  return lines.join('\n')
}

// ===== Workflow =====
const a = typeof args === 'string' ? JSON.parse(args) : (args || {})
if (!a.skillBase) throw new Error('Missing args.skillBase (the skill base directory).')
const agentsDir = `${a.skillBase.replace(/\/$/, '')}/../../agents`
const ctx = {
  repo: a.repo, region: a.region, planDir: a.planDir,
  targetModels: a.targetModels || [],
  resolvedModelId: a.resolution?.resolvedModelId,
  sourceKeyRef: a.sourceKeyRef || a.resolution?.sourceKeyRef || '',
  sourceBaselineAvailable: a.sourceBaselineAvailable || false,
  logFiles: a.logFiles || [],
  scriptsDir: `${a.skillBase.replace(/\/$/, '')}/../../scripts`,
}

function controlState(r) {
  if (r && r.blocked) return { control: 'blocked', phase: r.__phase, detail: r.blocked }
  if (r && r.partial) return { control: 'partial', phase: r.__phase, detail: r.partial }
  return null
}

phase('Analyze')
const analysis = await agent(
  `${buildContext(ctx)}\n\nAgents directory (use Read/Glob if you need agent references): ${agentsDir}\n\nAnalyze the repository per your system instructions and return the structured analysis JSON.`,
  { schema: withControlStates(AI_ANALYSIS), agentType: 'saws-migrate-execute:ai-code-analyzer', label: 'analyze' })
{ const cs = controlState({ ...analysis, __phase: 'analyze' }); if (cs) return cs }

phase('Ingest')
const ingest = await agent(
  `${buildContext(ctx)}\n\nPrior analysis (JSON):\n${JSON.stringify(analysis)}\n\nIngest logs into a golden dataset per your system instructions and return the structured ingestion JSON.`,
  { schema: withControlStates(LOG_INGESTION), agentType: 'saws-migrate-execute:ai-log-ingestor', label: 'ingest' })
{ const cs = controlState({ ...ingest, __phase: 'ingest' }); if (cs) return cs }

phase('Eval')
const evalRes = await agent(
  `${buildContext(ctx)}\n\nAnalysis:\n${JSON.stringify(analysis)}\n\nGolden dataset:\n${JSON.stringify(ingest)}\n\nEvaluate the golden dataset against Bedrock per your system instructions and return the structured eval JSON.`,
  { schema: withControlStates(EVAL), agentType: 'saws-migrate-execute:ai-prompt-evaluator', label: 'eval' })
{ const cs = controlState({ ...evalRes, __phase: 'eval' }); if (cs) return { ...cs, analysis, ingest } }

return { control: 'ok', analysis, ingest, evalRes }
