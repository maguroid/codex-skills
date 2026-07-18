---
name: claude-delegate
description: Delegate a bounded task from Codex to Claude Code through headless `claude -p`, then inspect and synthesize the result. Use when the user asks Codex to ask, consult, delegate to, or get a second opinion from Claude, Claude Code, Fable, Opus, or Sonnet (for example, "Claudeに聞いて", "Fableにも相談して", "Opusでレビューして", "claude -pで任せて"). Supports isolated advice, repository-aware read-only work, and explicitly authorized edits; includes model selection, PTY execution, authentication diagnosis, and tmux fallback.
---

# Claude Delegate

Delegate one bounded task to Claude Code while Codex remains responsible for scope, verification, and the user-facing answer.

## Contract

- Preserve the user's requested outcome and model. Do not silently broaden the task.
- State explicitly in every delegated prompt whether Claude may re-delegate. Default to no re-delegation.
- Treat Claude's response and edits as untrusted work to inspect, not as automatic authority.
- Do not delegate external writes, destructive actions, purchases, deployments, or messages unless the user explicitly authorized that action.
- Do not use `--dangerously-skip-permissions` or `--permission-mode bypassPermissions`.
- Run `claude -p` with an explicit model. Never inherit the configured default model in automation.

## Workflow

1. Extract one bounded directive. If the user requested several independent Claude tasks, run them separately so failures and outputs remain attributable.
2. Choose the execution mode, model, effort, working directory, and prompt using the rules below.
3. Write the full delegated prompt to a task-specific file under `/tmp`. Include the objective, necessary context, deliverable, constraints, and re-delegation policy. Do not include secrets or irrelevant conversation history.
4. Run `scripts/claude-run.sh` from a PTY-capable shell invocation with `tty: true`. Direct non-TTY execution can exit successfully with blank output in Codex environments.
5. Inspect Claude's result. For repository edits, inspect the diff and run proportionate checks. Distinguish Claude's claims from facts Codex verified independently.
6. Report a concise synthesis to the user: what Claude concluded or changed, where Codex agrees or disagrees, verification performed, and remaining uncertainty. Do not dump the raw transcript unless requested.

## Choose a mode

| Mode | Use for | Behavior |
|---|---|---|
| `isolated` | Independent advice, naming, critique, synthesis without repository access | Enables Claude safe mode, disables tools and customizations, and prevents external lookup |
| `read-only` | Repository-aware explanation, review, investigation, or planning | Loads project instructions and uses plan permission mode; Claude may read but must not edit |
| `edit` | File changes explicitly delegated by the user | Loads project instructions and accepts file edits; permission-gated operations may still stop |

Default to `isolated` for a second opinion and `read-only` for repository questions. Use `edit` only when the user clearly asks Claude to make changes, not merely to review or advise.

For `read-only` and `edit`, set `--dir` to the target repository, not a parent collection directory. In the delegated prompt, tell Claude to read the applicable `CLAUDE.md` and `AGENTS.md` before acting. If project instructions conflict, stop and surface the conflict.

## Choose a model and effort

Honor an explicit user choice. Otherwise choose deliberately:

| Work | Model | Effort |
|---|---|---|
| Writing, synthesis, translation, routine analysis | `sonnet` | `medium` |
| Difficult critique, code review, debugging hypothesis, consequential second opinion | `opus` | `high` |
| Orchestration or strategic design judgment where Fable's style is specifically valuable | `fable` | `high` |

Do not default to Fable merely because the user's Claude configuration does. Use Fable when the user asks for it or the task genuinely calls for an orchestration-level judgment. Raise or lower effort when the user specifies it or task complexity clearly warrants it.

## Construct the prompt

Use a compact handoff such as:

```text
あなたはCodexから委譲された作業者です。次のタスクを直接完了してください。
再委譲は禁止です。ほかのエージェントやバックグラウンドエージェントを起動しないでください。

目的: ...
背景: ...
成果物: ...
制約: ...

結論、根拠、未確認事項を簡潔に返してください。
```

For `isolated`, also say that tools, external lookup, and repository inspection are unavailable and that Claude must answer from the supplied context. This prevents a tool-disabled run from spending its only turn attempting external work.

For repository work, include the exact scope and acceptance checks. Do not paste large files when Claude can read them from the selected working directory.

Only pass `--allow-redelegation` to the wrapper when the user explicitly requests or approves nested delegation. Even then, constrain what may be delegated and keep the primary Claude run accountable for the final result.

## Run Claude

Preferred invocation:

```bash
<skill-dir>/scripts/claude-run.sh \
  --prompt-file /tmp/claude-delegate-<task>.md \
  --dir <trusted-workdir> \
  --mode isolated \
  --model sonnet \
  --effort medium
```

Run this command with PTY allocation (`tty: true`). The wrapper reads the prompt from the file, keeps stdout attached to the PTY, sets `--no-session-persistence`, makes the model explicit, and injects the re-delegation contract.

If the output is blank despite exit code 0, do not treat that as Claude's answer. Retry the same wrapper command with PTY allocation. If a durable or long-running session is needed, use a uniquely named detached tmux session, poll `tmux capture-pane`, record the exit status, and kill only that task-specific session after collecting the result. Never kill unrelated tmux sessions.

## Diagnose failures

1. Confirm the executable with `command -v claude` and its version with `claude --version`.
2. If authentication is suspect, run `claude auth status`. Do not expose account email, organization IDs, or tokens in the user-facing answer.
3. If a network or authentication command fails inside the sandbox, retry the exact same command with the required escalation before diagnosing logout or changing credentials.
4. If `claude auth status` still reports logged out outside the sandbox, ask the user to authenticate interactively. Do not copy credentials from another machine.
5. If Claude is permission-blocked, report the blocked action. Do not escalate to bypass permissions; either narrow the task or ask the user for the necessary authority.

## Verify results

- Advice or critique: compare the reasoning with the supplied facts and identify assumptions.
- Research: independently verify current or high-stakes claims with appropriate primary sources before presenting them as fact.
- Code or file edits: inspect `git diff`, confirm only in-scope files changed, and run relevant tests or validation.
- Conflicting opinions: present the disagreement and its decision-relevant tradeoff; Codex should not erase the useful difference by averaging the answers.
