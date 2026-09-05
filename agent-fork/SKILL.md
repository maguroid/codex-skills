---
name: agent-fork
description: "Fork the current Codex context into a side agent only on explicit $agent-fork, /agent-fork, or named invocation; not ordinary delegation."
---

# Agent Fork

## Contract

Create one Codex side agent for each explicitly requested fork:

- Inherit the conversation and instructions available at the spawn point.
- Run one bounded directive independently, preferably in the background.
- Keep the side agent's intermediate tool traffic out of the main conversation.
- Return the side agent's final result to the main conversation.
- Let the main agent continue other work instead of duplicating the forked directive.

Do not create a user-owned thread, task, or session unless the user explicitly asks for one. A fork is a child of the current conversation, not a handoff to a separate user-facing conversation.

## Workflow

1. Parse the directive after the explicit invocation and remove the invocation token. Preserve the user's wording. If no directive remains, ask for the fork's task and stop.
2. Decide whether the directive is read-only or mutating. Fork read-only analysis, review, research, comparison, and test planning directly. For edits, check the filesystem isolation rules below before spawning.
3. Call `spawn_agent` with `fork_turns: "all"`, a short unique `task_name` derived from the directive using lowercase letters, digits, and underscores, and the prepared fork instruction. If this Codex environment does not expose `spawn_agent` with full-context inheritance, state that the fork contract is unsupported. Do not silently substitute a fresh-context agent, user-owned thread, or unrelated workflow.
4. Start the fork without another confirmation. The explicit skill invocation authorizes the child spawn, but does not authorize external writes, messages, deployments, purchases, or destructive operations beyond the directive.
5. Continue any distinct main-agent work already in progress. If the user requested only the forked task, wait for its result instead of performing the same task in parallel.
6. When the fork finishes, label its result clearly, verify material claims or edits in proportion to risk, and synthesize only where that improves usability.

## Fork Instruction

Pass the user's directive together with only the operational constraints that are not already inherited:

- Work only on the stated directive.
- Do not re-delegate or spawn additional agents.
- Follow inherited user, project, repository, and safety instructions.
- Treat the user's latest message as authoritative when it changes earlier context.
- Avoid external or destructive state changes unless the directive explicitly authorizes them.
- Return a concise final result, including evidence, changed files, and verification when applicable.

## Filesystem Isolation

Conversation forking does not necessarily fork the filesystem.

- Prefer read-only fork directives when the main agent remains active in the same working tree.
- If the fork and main agent may edit overlapping files, use native worktree or equivalent filesystem isolation when available.
- Without isolation, do not allow concurrent overlapping edits. Narrow one side to read-only work, sequence the edits, or ask the user which side should own the files.
- Treat child edits as untrusted shared-worktree changes until the main agent inspects the diff and runs appropriate verification.

## Manual Invocation

This skill is manual-only. Do not infer an invocation from phrases such as "delegate this," "run in parallel," "get another opinion," or "use a subagent." Use it only when the user explicitly invokes `$agent-fork`, `/agent-fork`, or the `agent-fork` skill by name.
