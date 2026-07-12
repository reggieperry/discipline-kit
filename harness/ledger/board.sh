#!/bin/sh
# ledger/board.sh — read-only views over the dev-ledger (ledger/claims.jsonl + ledger/trace/).
#
# The board READS; humans and the gate WRITE. There are deliberately no write subcommands
# here — a claim is minted through `ledger/append`, retired through `ledger/retire`, and
# signed only by `ledger/gate.py`. See .claude/skills/ledger-board/SKILL.md for when to run
# which view; the entry, preregister, discharge, retire, and verify disciplines are their
# own skills.
#
# Subcommands:
#   open              unverified assertions still awaiting a check — the research program at a glance
#   stale [days]      unverified assertions older than N days (default 30) — the unexamined-beliefs alarm
#   graveyard         refuted and contested claims with their refutation pointers — the do-not-rebuild list
#   checks            check-name histogram over the live board — which verifiers earn their keep
#   find <keyword>    case-insensitive match over claim text, any status, live + trace — the have-we-been-here query
#   next-id           the next clm-NNNN in sequence, computed not guessed
#   --selftest        run every subcommand against ledger/fixtures/board-fixture.jsonl and assert exact output
#
# Determinism: age is measured against LEDGER_BOARD_NOW (epoch seconds) when set, else the
# wall clock; --selftest pins it so the fixture ages never drift. The ledger file is
# LEDGER_FILE (default ledger/claims.jsonl); --selftest points it at the fixture.
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
LEDGER_FILE=${LEDGER_FILE:-"$ROOT/ledger/claims.jsonl"}
NOW=${LEDGER_BOARD_NOW:-$(date -u +%s)}

die() { echo "board.sh: $*" >&2; exit 3; }
command -v jq >/dev/null 2>&1 || die "jq is required (not found on PATH)"

# The live board (one file) and the live+trace set (adds sibling trace/*.jsonl if present).
# open/stale/checks read the live board; find/graveyard/next-id read live+trace so a retired
# or defeated idea is still found and ids never collide with a traced one.
live_files() { printf '%s\n' "$LEDGER_FILE"; }
all_files() {
  printf '%s\n' "$LEDGER_FILE"
  tracedir="$(dirname -- "$LEDGER_FILE")/trace"
  [ -d "$tracedir" ] || return 0
  for f in "$tracedir"/*.jsonl; do [ -e "$f" ] && printf '%s\n' "$f"; done
}

# jq over a newline-list of files on stdin (word-splitting is safe: ledger paths have no spaces).
jq_over() { _prog=$1; shift; _files=$(cat); jq "$@" -r "$_prog" $_files; }

cmd_open() {
  live_files | jq_over '
    (map(select(.supersedes) | .supersedes)) as $sup
    | sort_by(.id)[] | . as $e
    | select($e.kind=="assertion" and $e.status=="unverified" and (($sup | index($e.id)) | not))
    | "\($e.id)  \($e.claim[0:80])  (\((($now - ($e.ts|fromdateiso8601))/86400)|floor)d)"
  ' -s --argjson now "$NOW"
}

cmd_stale() {
  days=${1:-30}
  live_files | jq_over '
    (map(select(.supersedes) | .supersedes)) as $sup
    | sort_by(.id)[] | . as $e
    | select($e.kind=="assertion" and $e.status=="unverified" and (($sup | index($e.id)) | not))
    | ((($now - ($e.ts|fromdateiso8601))/86400)|floor) as $age
    | select($age > $days)
    | "\($e.id)  \($e.claim[0:80])  (\($age)d)"
  ' -s --argjson now "$NOW" --argjson days "$days"
}

cmd_graveyard() {
  all_files | jq_over '
    (map(select(.supersedes) | .supersedes)) as $sup
    | (map(select(.kind=="refutation" and .about))) as $refs
    | ($refs | map(.about)) as $refabout
    | sort_by(.id)[] | . as $e
    | if ($e.kind=="assertion" and $e.status=="refuted") then
        "\($e.id)  \($e.claim[0:80])  [refuted \($e.discharged_by.run // $e.check)]"
      elif ($e.kind=="assertion" and ($e.status=="unverified" or $e.status=="signed")
            and ($refabout | index($e.id)) and (($sup | index($e.id)) | not)) then
        "\($e.id)  \($e.claim[0:80])  [contested by \($refs | map(select(.about==$e.id) | .id) | join(","))]"
      else empty end
  ' -s
}

cmd_checks() {
  live_files | jq_over '
    map(.check // "none")
    | reduce .[] as $c ({}; .[$c] += 1)
    | to_entries | sort_by([-.value, .key])[]
    | "\(.value)  \(.key)"
  ' -s
}

cmd_find() {
  [ $# -ge 1 ] || die "usage: board.sh find <keyword>"
  all_files | jq_over '
    ($kw | ascii_downcase) as $k
    | sort_by(.id)[]
    | select((.claim // "") | ascii_downcase | contains($k))
    | "\(.id)  [\(.status)]  \(.claim[0:80])"
  ' -s --arg kw "$1"
}

cmd_next_id() {
  all_files | jq_over '
    [ .[].id | select(type=="string" and test("^clm-[0-9]+$")) | ltrimstr("clm-") | tonumber ]
    | ((max // 0) + 1) as $n
    | "clm-\(("0000" + ($n | tostring))[-4:])"
  ' -s
}

selftest() {
  fixture="$ROOT/ledger/fixtures/board-fixture.jsonl"
  [ -f "$fixture" ] || die "selftest: fixture missing at $fixture"
  LEDGER_FILE="$fixture"
  # A fixed clock so the fixture ages are exact and the assertions never drift.
  NOW=$(printf '%s' '"2026-07-11T00:00:00Z"' | jq 'fromdateiso8601')
  fails=0
  _case() {
    _name=$1; shift
    _got=$("$@")
    _want=$(expected "$_name")
    if [ "$_got" = "$_want" ]; then
      printf 'ok    %s\n' "$_name"
    else
      fails=$((fails + 1))
      printf 'DRIFT %s\n' "$_name"
      printf '  --- want ---\n%s\n  --- got ---\n%s\n' "$_want" "$_got" | sed 's/^/  /'
    fi
  }
  _case open       cmd_open
  _case stale      cmd_stale
  _case stale5     cmd_stale 5
  _case graveyard  cmd_graveyard
  _case checks     cmd_checks
  _case find-cache cmd_find cache
  _case find-comb  cmd_find combiner
  _case next-id    cmd_next_id
  if [ "$fails" -eq 0 ]; then
    echo "board.sh --selftest: all views green against the committed fixture"
    return 0
  fi
  echo "board.sh --selftest: $fails view(s) drifted from the committed fixture" >&2
  return 1
}

# EXPECTED OUTPUTS — baked from a run against the committed fixture; --selftest is red on any drift.
expected() {
  case "$1" in
  open) cat <<'EOF'
clm-0001  widget throughput exceeds the documented baseline under sustained production loa  (71d)
clm-0008  the cache hit rate holds above ninety percent in production traffic  (10d)
clm-0010  the parked battery is wired into the repo check before landing  (5d)
EOF
  ;;
  stale) cat <<'EOF'
clm-0001  widget throughput exceeds the documented baseline under sustained production loa  (71d)
EOF
  ;;
  stale5) cat <<'EOF'
clm-0001  widget throughput exceeds the documented baseline under sustained production loa  (71d)
clm-0008  the cache hit rate holds above ninety percent in production traffic  (10d)
EOF
  ;;
  graveyard) cat <<'EOF'
clm-0006  the fast path removes the extra allocation on the hot loop  [refuted repo-check@bad9999+cc33dd44]
clm-0008  the cache hit rate holds above ninety percent in production traffic  [contested by clm-0007]
EOF
  ;;
  checks) cat <<'EOF'
3  none
3  repo-check
2  scala-suite
1  deep-reason
1  ledger-skills-selftest
EOF
  ;;
  find-cache) cat <<'EOF'
clm-0007  [unverified]  profiling shows the ninety-percent cache-hit figure does not reproduce
clm-0008  [unverified]  the cache hit rate holds above ninety percent in production traffic
EOF
  ;;
  find-comb) cat <<'EOF'
clm-0004  [signed]  the corroboration combiner satisfies the commutative-monoid laws
clm-0009  [retired]  an earlier draft of the combiner-laws claim, now superseded by the signed statem
EOF
  ;;
  next-id) cat <<'EOF'
clm-0011
EOF
  ;;
  esac
}

usage() {
  # Print the leading comment block (minus the shebang), stripping the comment marker.
  awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"
}

main() {
  [ $# -ge 1 ] || { usage; exit 2; }
  sub=$1; shift
  case "$sub" in
    open)       cmd_open "$@" ;;
    stale)      cmd_stale "$@" ;;
    graveyard)  cmd_graveyard "$@" ;;
    checks)     cmd_checks "$@" ;;
    find)       cmd_find "$@" ;;
    next-id)    cmd_next_id "$@" ;;
    --selftest) selftest ;;
    -h|--help)  usage ;;
    *)          die "unknown subcommand '$sub' (try --help)" ;;
  esac
}

main "$@"
