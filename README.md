# saws-migrate-execute

A Claude Code plugin that executes AI-only (Gemini/OpenAI → Amazon Bedrock) migration plans.

## What it does

Given a Track 2 migration plan (produced by the `saws-migrate` planning skill), this plugin:
1. Analyzes your source code to detect LLM SDK calls
2. Builds a golden dataset of prompt/response pairs
3. Evaluates prompts against Bedrock (with optional source-model side-by-side comparison)
4. Rewrites your code on an isolated `bedrock-migration` git branch
5. Generates a comprehensive migration report

## Prerequisites

- Claude Code
- Python 3.10+ and `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- AWS credentials with `bedrock:InvokeModel` permission on target model(s)
- A Track 2 migration plan (generate one with the `saws-migrate` planning skill)

## Installation

```bash
/plugin marketplace add leon1418/saws-migrate-execute-plugin
/plugin install saws-migrate-execute@saws-migrate
```

## Usage

```bash
/saws-migrate-execute:migrate-execute
```

The plugin discovers available plans and guides you through the process interactively.

## Architecture

- **commands/** — `/migrate-execute` entry point
- **skills/migrate-execute/** — orchestration skill (readiness → preflight → workflow run 1 → checkpoint → workflow run 2 → report)
- **agents/** — 5 specialized subagents (analyzer, log-ingestor, evaluator, rewriter, report-generator)
- **skills/** — vendored supporting skills (execution-readiness, behavior-delta-detection, resolve-bedrock-model-id, etc.)
- **scripts/** — Python utilities (Bedrock preflight probe, pricing lookup) with pinned `uv` toolchain

## License

MIT
