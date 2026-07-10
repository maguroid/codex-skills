---
name: agent-fork
description: Manual-only workflow for forking the current conversation into a background side agent that inherits the available context, runs one bounded directive while the main agent can continue, and returns its final result. Use only when the user explicitly invokes `$agent-fork`, `/agent-fork`, or names the agent-fork skill; never trigger implicitly for ordinary delegation, parallel work, review, or research requests.
---

# Agent Fork

## Contract

Create one side agent for each explicitly requested fork. Preserve these semantics as closely as the active harness allows:

- Inherit the conversation and instructions available at the spawn point.
- Run one bounded directive independently, preferably in the background.
- Keep the side agent's intermediate tool traffic out of the main conversation.
- Return the side agent's final result to the main conversation.
- Let the main agent continue other work instead of duplicating the forked directive.

Do not create a user-owned thread, task, or session unless the user explicitly asks for one. A fork is a child of the current conversation, not a handoff to a separate user-facing conversation.

## Workflow

1. Parse the directive after the explicit invocation and remove the invocation token. Preserve the user's wording. If no directive remains, ask for the fork's task and stop.
2. Decide whether the directive is read-only or mutating. Fork read-only analysis, review, research, comparison, and test planning directly. For edits, check the filesystem isolation rules below before spawning.
3. Select the strongest available adapter:
   - If the harness exposes native conversation forking, use it.
   - In Codex, call `spawn_agent` with `fork_turns: "all"`, a short unique task name derived from the directive, and the prepared fork instruction.
   - If only fresh-context subagents exist, emulate a fork only when the necessary context can be faithfully packaged into the spawn instruction. Tell the user that full context inheritance is unavailable.
   - If the harness cannot return child results to the current conversation, state that the fork contract is unsupported and offer a handoff as a separate action. Do not silently substitute an unrelated workflow.
4. Start the fork without another confirmation. The explicit skill invocation authorizes the child spawn, but does not authorize external writes, messages, deployments, purchases, or destructive operations beyond the directive.
5. Continue any distinct main-agent work already in progress. If the user requested only the forked task, wait for its result instead of performing the same task in parallel.
6. When the fork finishes, label its result clearly, verify material claims or edits in proportion to risk, and synthesize only where that improves usability.

Claude Code's built-in `/fork` already implements the native behavior and takes precedence over this compatibility skill. Do not attempt to emulate it inside Claude Code when the built-in command handled the invocation.

## Fork Instruction

Pass the user's directive together with only the operational constraints that are not already inherited:

- Work only on the stated directive.
- Do not re-delegate or spawn additional agents.
- Follow inherited user, project, repository, and safety instructions.
- Treat the user's latest message as authoritative when it changes earlier context.
- Avoid external or destructive state changes unless the directive explicitly authorizes them.
- Return a concise final result, including evidence, changed files, and verification when applicable.

When full conversation inheritance is unavailable, also include the minimum faithful handoff: objective, relevant decisions, constraints, authoritative files or briefs, current state, expected output, and where the result should return. Do not dump unrelated history.

## Filesystem Isolation

Conversation forking does not necessarily fork the filesystem.

- Prefer read-only fork directives when the main agent remains active in the same working tree.
- If the fork and main agent may edit overlapping files, use native worktree or equivalent filesystem isolation when available.
- Without isolation, do not allow concurrent overlapping edits. Narrow one side to read-only work, sequence the edits, or ask the user which side should own the files.
- Treat child edits as untrusted shared-worktree changes until the main agent inspects the diff and runs appropriate verification.

## Manual Invocation

This skill is manual-only. Do not infer an invocation from phrases such as "delegate this," "run in parallel," "get another opinion," or "use a subagent." Use it only when the user explicitly invokes `$agent-fork`, `/agent-fork`, or the `agent-fork` skill by name.
