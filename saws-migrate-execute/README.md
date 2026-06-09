# saws-migrate-execute

Claude Code plugin that executes a Track 2 (AI-only → Amazon Bedrock) migration plan.

Prerequisites: `python3`, `uv`, and AWS credentials with `bedrock:InvokeModel` on the target model(s).
Run `/migrate-execute <path-to-plan>` with a plan produced by the `saws-migrate` planning skill.
