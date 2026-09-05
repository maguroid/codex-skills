---
name: codex-log-db-control
description: "Inspect Codex/Orca logs_2.sqlite write churn or apply and verify the requested reversible logging workaround."
---

# Codex Log DB Control

Use the bundled script for deterministic discovery, backup, mutation, and verification:

```sh
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" status
```

The script auto-detects:

- `${CODEX_HOME}/logs_2.sqlite` when `CODEX_HOME` is set
- `$HOME/.codex/logs_2.sqlite`
- `$HOME/Library/Application Support/orca/codex-runtime-home/home/logs_2.sqlite`

Pass `--db PATH` one or more times to target other or specific databases.

## Safety contract

- Treat this as an unsupported, local workaround for Codex internals. Codex has no supported setting that disables only this database.
- Explain that `logs_2.sqlite` stores bounded local diagnostic tracing used for troubleshooting and feedback; it is not conversation history.
- Do not claim `[analytics] enabled = false`, `[feedback] enabled = false`, `RUST_LOG`, or disabling OTel exporters stops these local writes.
- Run `status` before any mutation and resolve the exact target databases.
- Obtain explicit user authorization before `disable`, `enable`, or `compact`; these commands additionally require `--yes`.
- Preserve every backup the script creates. Never overwrite or delete one automatically.
- Do not use `compact` unless insert suppression is active. It rewrites the database once to reclaim free pages.
- Re-run `status` and `verify` after Codex or Orca updates because a migration may remove the trigger.

## Workflows

### Inspect

```sh
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" status
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" verify --seconds 15
```

Report per database:

- database and WAL sizes
- row count and maximum row ID
- free-page ratio
- trigger state
- quick integrity result
- whether rows or SQLite data changed during verification

Large gaps between maximum ID and row count, a high free-page ratio, or continuing changes during `verify` indicate churn. A stable sample does not prove there was no historic churn.

### Disable new diagnostic-log inserts

```sh
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" disable --yes
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" verify --seconds 15
```

`disable` first creates a consistent compact backup, verifies it, then adds a `BEFORE INSERT` trigger using `RAISE(IGNORE)`. Existing rows remain readable. New inserts report success to SQLite but add no row.

After verification succeeds, reclaim accumulated free pages only when requested:

```sh
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" compact --yes
```

### Restore inserts

```sh
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" enable --yes
python3 "$HOME/.codex/skills/codex-log-db-control/scripts/codex_log_db.py" verify --seconds 15
```

`enable` drops only the trigger managed by this skill. Do not restore an old database merely to re-enable writes.

## Interpretation

Disabling inserts sacrifices new local diagnostic records, especially evidence available to `/feedback` and maintainers investigating failures. It does not disable all Codex telemetry, conversation persistence, or arbitrary filesystem writes. If Codex begins failing after suppression, restore inserts first and report the behavior as a compatibility issue.
