#!/usr/bin/env python3
"""Inspect and control Codex local diagnostic log SQLite databases."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


TRIGGER_NAME = "codex_disable_log_insert"
TRIGGER_SQL = f"""
CREATE TRIGGER IF NOT EXISTS {TRIGGER_NAME}
BEFORE INSERT ON logs
BEGIN
  SELECT RAISE(IGNORE);
END
"""


@dataclass(frozen=True)
class Snapshot:
    row_count: int
    max_id: int | None
    data_version: int
    db_size: int
    wal_size: int
    db_mtime_ns: int
    wal_mtime_ns: int


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def file_stat(path: Path) -> tuple[int, int]:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return 0, 0
    return stat.st_size, stat.st_mtime_ns


def read_only_connection(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(path), safe='/')}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def writable_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=30)
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def validate_schema(connection: sqlite3.Connection, path: Path) -> None:
    row = connection.execute(
        "SELECT 1 FROM sqlite_schema WHERE type = 'table' AND name = 'logs'"
    ).fetchone()
    if row is None:
        raise RuntimeError(f"{path}: expected table 'logs' was not found")


def trigger_enabled(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_schema WHERE type = 'trigger' AND name = ?",
            (TRIGGER_NAME,),
        ).fetchone()
        is not None
    )


def snapshot(connection: sqlite3.Connection, path: Path) -> Snapshot:
    count, maximum = connection.execute(
        "SELECT count(*), max(id) FROM logs"
    ).fetchone()
    data_version = connection.execute("PRAGMA data_version").fetchone()[0]
    db_size, db_mtime = file_stat(path)
    wal_size, wal_mtime = file_stat(Path(f"{path}-wal"))
    return Snapshot(
        row_count=count,
        max_id=maximum,
        data_version=data_version,
        db_size=db_size,
        wal_size=wal_size,
        db_mtime_ns=db_mtime,
        wal_mtime_ns=wal_mtime,
    )


def discover_databases(explicit: list[str]) -> list[Path]:
    candidates: list[Path] = []
    if explicit:
        candidates.extend(Path(item).expanduser() for item in explicit)
    else:
        codex_home = os.environ.get("CODEX_HOME")
        if codex_home:
            candidates.append(Path(codex_home).expanduser() / "logs_2.sqlite")
        candidates.extend(
            [
                Path.home() / ".codex" / "logs_2.sqlite",
                Path.home()
                / "Library"
                / "Application Support"
                / "orca"
                / "codex-runtime-home"
                / "home"
                / "logs_2.sqlite",
            ]
        )

    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        absolute = candidate.absolute()
        key = str(absolute)
        if key in seen:
            continue
        seen.add(key)
        if explicit and not absolute.is_file():
            raise FileNotFoundError(f"database not found: {absolute}")
        if absolute.is_file():
            result.append(absolute)
    if not result:
        raise FileNotFoundError("no Codex logs_2.sqlite databases found")
    return result


def make_backup(path: Path, reason: str) -> Path:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    backup_dir = path.parent / f"logs-backup-{timestamp}-{reason}"
    suffix = 1
    while backup_dir.exists():
        backup_dir = path.parent / f"logs-backup-{timestamp}-{reason}-{suffix}"
        suffix += 1
    backup_dir.mkdir(mode=0o700)
    backup_path = backup_dir / f"{path.stem}.compact.sqlite"

    with writable_connection(path) as connection:
        validate_schema(connection, path)
        quoted = str(backup_path).replace("'", "''")
        connection.execute(f"VACUUM INTO '{quoted}'")

    with read_only_connection(backup_path) as backup:
        result = backup.execute("PRAGMA quick_check").fetchone()[0]
    if result != "ok":
        raise RuntimeError(f"backup integrity check failed: {backup_path}: {result}")
    return backup_path


def checkpoint(connection: sqlite3.Connection) -> tuple[int, int, int]:
    return connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()


def status_one(path: Path) -> None:
    with read_only_connection(path) as connection:
        validate_schema(connection, path)
        current = snapshot(connection, path)
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        free_count = connection.execute("PRAGMA freelist_count").fetchone()[0]
        quick_check = connection.execute("PRAGMA quick_check").fetchone()[0]
        enabled = trigger_enabled(connection)
    free_ratio = (free_count / page_count * 100) if page_count else 0
    print(path)
    print(f"  inserts: {'disabled' if enabled else 'enabled'}")
    print(
        f"  rows: {current.row_count}, max_id: "
        f"{current.max_id if current.max_id is not None else 'null'}"
    )
    print(
        f"  database: {format_bytes(current.db_size)}, "
        f"WAL: {format_bytes(current.wal_size)}"
    )
    print(
        f"  pages: {page_count}, free: {free_count} ({free_ratio:.1f}%), "
        f"quick_check: {quick_check}"
    )


def disable_one(path: Path) -> None:
    with read_only_connection(path) as connection:
        validate_schema(connection, path)
        if trigger_enabled(connection):
            print(f"{path}: inserts already disabled")
            return
    backup = make_backup(path, "disable-log-inserts")
    with writable_connection(path) as connection:
        validate_schema(connection, path)
        connection.execute(TRIGGER_SQL)
        connection.commit()
        checkpoint_result = checkpoint(connection)
        if not trigger_enabled(connection):
            raise RuntimeError(f"{path}: trigger creation could not be verified")
    print(f"{path}: inserts disabled")
    print(f"  backup: {backup}")
    print(f"  checkpoint: {checkpoint_result}")


def enable_one(path: Path) -> None:
    with writable_connection(path) as connection:
        validate_schema(connection, path)
        existed = trigger_enabled(connection)
        connection.execute(f"DROP TRIGGER IF EXISTS {TRIGGER_NAME}")
        connection.commit()
        checkpoint_result = checkpoint(connection)
        if trigger_enabled(connection):
            raise RuntimeError(f"{path}: trigger removal could not be verified")
    state = "inserts enabled" if existed else "inserts already enabled"
    print(f"{path}: {state}")
    print(f"  checkpoint: {checkpoint_result}")


def compact_one(path: Path) -> None:
    with read_only_connection(path) as connection:
        validate_schema(connection, path)
        if not trigger_enabled(connection):
            raise RuntimeError(
                f"{path}: refusing to compact while inserts are enabled; "
                "disable them first"
            )
    backup = make_backup(path, "before-compact")
    before, _ = file_stat(path)
    with writable_connection(path) as connection:
        validate_schema(connection, path)
        if not trigger_enabled(connection):
            raise RuntimeError(f"{path}: insert suppression disappeared")
        connection.execute("VACUUM")
        checkpoint_result = checkpoint(connection)
    after, _ = file_stat(path)
    print(f"{path}: compacted {format_bytes(before)} -> {format_bytes(after)}")
    print(f"  backup: {backup}")
    print(f"  checkpoint: {checkpoint_result}")


def report_verification(
    path: Path,
    seconds: float,
    disabled: bool,
    before: Snapshot,
    after: Snapshot,
) -> bool:
    rows_changed = (before.row_count, before.max_id) != (
        after.row_count,
        after.max_id,
    )
    data_changed = before.data_version != after.data_version
    wal_grew = after.wal_size > before.wal_size
    stable = not rows_changed and not data_changed and not wal_grew
    print(path)
    print(f"  inserts: {'disabled' if disabled else 'enabled'}")
    print(
        f"  sample: {seconds:g}s, rows: {before.row_count} -> {after.row_count}, "
        f"max_id: {before.max_id} -> {after.max_id}"
    )
    print(
        f"  data_version: {before.data_version} -> {after.data_version}, "
        f"WAL: {format_bytes(before.wal_size)} -> {format_bytes(after.wal_size)}"
    )
    print(f"  result: {'stable' if stable else 'changed'}")
    return stable


def verify_databases(paths: list[Path], seconds: float) -> bool:
    with ExitStack() as stack:
        samples: list[tuple[Path, sqlite3.Connection, bool, Snapshot]] = []
        for path in paths:
            connection = stack.enter_context(read_only_connection(path))
            validate_schema(connection, path)
            before = snapshot(connection, path)
            disabled = trigger_enabled(connection)
            samples.append((path, connection, disabled, before))
        time.sleep(seconds)
        results = [
            report_verification(
                path,
                seconds,
                disabled,
                before,
                snapshot(connection, path),
            )
            for path, connection, disabled, before in samples
        ]
    return all(results)


def add_db_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        action="append",
        default=[],
        metavar="PATH",
        help="target a specific database; repeat for multiple databases",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect and control Codex logs_2.sqlite writes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="inspect databases")
    add_db_option(status_parser)

    verify_parser = subparsers.add_parser(
        "verify", help="sample databases for changes"
    )
    add_db_option(verify_parser)
    verify_parser.add_argument(
        "--seconds", type=float, default=15, help="sample duration (default: 15)"
    )

    for name, help_text in (
        ("disable", "back up databases and suppress new log inserts"),
        ("enable", "restore new log inserts"),
        ("compact", "back up and reclaim free pages after suppression"),
    ):
        action_parser = subparsers.add_parser(name, help=help_text)
        add_db_option(action_parser)
        action_parser.add_argument(
            "--yes", action="store_true", help="confirm the database mutation"
        )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if hasattr(args, "seconds") and args.seconds < 0:
        raise ValueError("--seconds must be non-negative")
    if args.command in {"disable", "enable", "compact"} and not args.yes:
        print(f"{args.command}: pass --yes after explicit user authorization", file=sys.stderr)
        return 2

    databases = discover_databases(args.db)
    if args.command == "status":
        for path in databases:
            status_one(path)
        return 0
    if args.command == "verify":
        return 0 if verify_databases(databases, args.seconds) else 1

    action = {
        "disable": disable_one,
        "enable": enable_one,
        "compact": compact_one,
    }[args.command]
    for path in databases:
        action(path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, RuntimeError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
