#!/usr/bin/env bash
# Seed the neighborhood story for memory strategy comparison.
#
# Usage:
#   ./scripts/seed_story.sh --memory <strategy> [--memory-dir <dir>]
#
# Strategies: profile_fixed  profile_evolving  episodic_fixed  episodic_evolving
#
# This story is intentionally non-corporate: neighbors, an injury, a family
# relationship, and a local store. A fixed hierarchy shaped for org-charts has
# no schema slots for these concepts and may silently drop some facts. An
# evolving hierarchy can discover and create new entity types on the fly.
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
    MEMORY_DIR="/tmp/${STRATEGY}/story"
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
run_chat "Dorothy plays hopscotch with her neighbor Theodore"
run_chat "Theodore trips and falls and his mom Betsy cleans his wound, and gives him a band-aid"
run_chat "Dorothy and Theodore go to the Sweet Spot to get ice cream and cool down"
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
echo "  Who are neighbors?"
echo "    -> Expect: Dorothy and Theodore."
echo "       Fixed hierarchy (org-chart schema) may have no 'neighbor' slot."
echo ""
echo "  Who was injured?"
echo "    -> Expect: Theodore."
echo "       Fixed hierarchy may have no 'injury event' category to store this."
echo ""
echo "  Who is Betsy?"
echo "    -> Expect: Theodore's mom."
echo "       Evolving hierarchy can create a 'family' or 'parent' node;"
echo "       fixed hierarchy may store only a 'person' profile with no relation."
echo ""
echo "  What store sells ice cream?"
echo "    -> Expect: The Sweet Spot."
echo "       Fixed hierarchy likely has no 'store' or 'location' schema slot;"
echo "       evolving hierarchy discovers and files it appropriately."
echo "================================================================"
