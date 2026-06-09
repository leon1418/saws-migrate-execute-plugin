# Fixture AI Migration Guide

## Overview

Minimal fixture for the e2e wiring smoke test. Migrates an OpenAI workload to Amazon Bedrock.

## Model Mapping

| Source Model | Target Model | Input Cost | Output Cost | Use Case Fit |
|--------------|--------------|------------|-------------|--------------|
| GPT-4o (OpenAI) | Claude Haiku 4.5 (`anthropic.claude-haiku-4-5-20251001-v1:0`) | $1.0/M | $5/M | Latency-sensitive moderate tasks. |
