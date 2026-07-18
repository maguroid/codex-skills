#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: claude-run.sh --prompt-file FILE --dir DIR --mode MODE --model MODEL [options]

Required:
  --prompt-file FILE       UTF-8 prompt file
  --dir DIR                Trusted working directory
  --mode MODE              isolated, read-only, or edit
  --model MODEL            Explicit Claude model or alias

Options:
  --effort LEVEL           low, medium, high, xhigh, or max (default: medium)
  --max-budget-usd AMOUNT  Optional print-mode budget ceiling
  --allow-redelegation     Explicitly permit nested delegation
  -h, --help               Show this help
EOF
}

prompt_file=""
work_dir=""
mode=""
model=""
effort="medium"
max_budget=""
allow_redelegation="false"

while (($#)); do
  case "$1" in
    --prompt-file)
      prompt_file="${2:?missing value for --prompt-file}"
      shift 2
      ;;
    --dir)
      work_dir="${2:?missing value for --dir}"
      shift 2
      ;;
    --mode)
      mode="${2:?missing value for --mode}"
      shift 2
      ;;
    --model)
      model="${2:?missing value for --model}"
      shift 2
      ;;
    --effort)
      effort="${2:?missing value for --effort}"
      shift 2
      ;;
    --max-budget-usd)
      max_budget="${2:?missing value for --max-budget-usd}"
      shift 2
      ;;
    --allow-redelegation)
      allow_redelegation="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$prompt_file" || -z "$work_dir" || -z "$mode" || -z "$model" ]]; then
  usage >&2
  exit 2
fi

if [[ ! -f "$prompt_file" || ! -r "$prompt_file" ]]; then
  printf 'Prompt file is not readable: %s\n' "$prompt_file" >&2
  exit 2
fi

if [[ ! -d "$work_dir" ]]; then
  printf 'Working directory does not exist: %s\n' "$work_dir" >&2
  exit 2
fi

case "$effort" in
  low|medium|high|xhigh|max) ;;
  *)
    printf 'Invalid effort: %s\n' "$effort" >&2
    exit 2
    ;;
esac

if ! command -v claude >/dev/null 2>&1; then
  printf 'claude executable was not found in PATH\n' >&2
  exit 127
fi

common_args=(
  -p
  --model "$model"
  --effort "$effort"
  --output-format text
  --no-session-persistence
)

case "$mode" in
  isolated)
    mode_args=(--safe-mode --tools "" --permission-mode dontAsk)
    ;;
  read-only)
    mode_args=(--permission-mode plan)
    ;;
  edit)
    mode_args=(--permission-mode acceptEdits)
    ;;
  *)
    printf 'Invalid mode: %s\n' "$mode" >&2
    exit 2
    ;;
esac

if [[ "$allow_redelegation" == "true" ]]; then
  delegation_contract='Nested delegation is explicitly allowed, but you remain responsible for the final result and must report what you delegated.'
else
  delegation_contract='Complete the delegated task directly. Do not delegate to other agents, background agents, or external coding agents.'
fi

common_args+=(--append-system-prompt "$delegation_contract")

if [[ -n "$max_budget" ]]; then
  common_args+=(--max-budget-usd "$max_budget")
fi

cd "$work_dir"
exec claude "${common_args[@]}" "${mode_args[@]}" < "$prompt_file"
