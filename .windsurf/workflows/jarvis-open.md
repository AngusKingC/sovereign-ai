---
name: jarvis-open
description: "Sovereign AI opening sequence — S0. Run this before starting any plan work. Verifies the previous tag exists on origin and confirms the working copy is clean."
---

# Jarvis Open — Plan Opening Sequence

Execute each step in order. Paste output for each. Do NOT skip steps.

## Step 1: Verify previous prompt's tag on origin
```powershell
git ls-remote --tags origin | Select-String "prompt-{N-1}"
```
If empty, STOP. Do not proceed — the previous plan's tag must exist before starting a new one.

## Step 2: Verify local working copy is clean and on master
```powershell
git status
git branch --show-current
git rev-parse HEAD
```
Do NOT pull. Confirm branch is `master` and there are no uncommitted changes.

**Note**: Changes to `GLM Prompts/` directory should be ignored for working copy cleanliness check — these are plan artifacts managed separately.

## Expected result

Tag verified, working copy clean. Only then proceed to the plan's own S0.3 (AGENTS.md rules, if any — this is plan-specific and lives in the plan file itself, not in this skill) and the plan body.
