#!/usr/bin/env bash
# Seed the corporate merger story for memory strategy comparison.
#
# Usage:
#   ./scripts/seed_corp.sh --memory <strategy> [--memory-dir <dir>]
#
# Strategies: profile_fixed  profile_evolving  episodic_fixed  episodic_evolving
#
# Each message is sent as a separate chat invocation (simulating distinct users
# logging in). After seeding, the script prints the command to run for
# interactive question answering.

set -euo pipefail

STRATEGY=""
MEMORY_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --memory)     STRATEGY="$2";    shift 2 ;;
        --memory-dir) MEMORY_DIR="$2";  shift 2 ;;
        *)
            echo "Unknown argument: $1"
            echo "Usage: $0 --memory <strategy> [--memory-dir <dir>]"
            exit 1
            ;;
    esac
done

if [[ -z "$STRATEGY" ]]; then
    echo "Usage: $0 --memory <strategy> [--memory-dir <dir>]"
    echo "Strategies: profile_fixed  profile_evolving  episodic_fixed  episodic_evolving"
    exit 1
fi

if [[ -z "$MEMORY_DIR" ]]; then
    MEMORY_DIR="/tmp/${STRATEGY}/corp"
fi

mkdir -p "$MEMORY_DIR"

echo "Strategy : $STRATEGY"
echo "Memory dir: $MEMORY_DIR"
echo ""

run_chat() {
    local message="$1"
    echo ">>> $message"
    printf '%s\nquit\n' "$message" | uv run chat --memory "$STRATEGY" --memory-dir "$MEMORY_DIR"
    echo ""
}

# ── Story ──────────────────────────────────────────────────────────────────
# Acme Corp employees
run_chat "Hi I am Tim, and I am the CEO of Acme Corp"
run_chat "Hello I am Amy and I am an engineer at Acme Corp"
run_chat "Hello this is Tim, and Amy is now working in the HR department"

# Zeta Corp employees
run_chat "Hello I am Mary and I am the CEO of Zeta Corp"
run_chat "Hello I am Josh and I am the accountant at Zeta Corp"
run_chat "Hello I am Josh and I now work in IT"

# Merger
run_chat "Hello this is Mary, Acme and Zeta have now merged into one company"
# ──────────────────────────────────────────────────────────────────────────

echo "================================================================"
echo "Seeding complete for strategy: $STRATEGY"
echo ""
echo "To ask questions, open an interactive session with:"
echo ""
echo "  uv run chat --memory \"$STRATEGY\" --memory-dir \"$MEMORY_DIR\""
echo ""
echo "Suggested questions (and what to watch for):"
echo ""
echo "  What companies exist?"
echo "    -> Expect: one merged entity. Profile may drop the original two names."
echo ""
echo "  What was Tim's role?"
echo "    -> Expect: CEO. Profile approaches should answer fine here (no update)."
echo ""
echo "  What is Josh's last role?"
echo "    -> Expect: IT. Profile will have overwritten Accountant; episodic keeps both."
echo ""
echo "  What is Amy's work history?"
echo "    -> Expect: Engineering -> HR -> merged company."
echo "       Profile will likely say only HR (Engineering overwritten)."
echo "       Episodic retains the full trajectory."
echo "================================================================"
