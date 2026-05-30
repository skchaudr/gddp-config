#!/usr/bin/env bash
set -euo pipefail
REPO="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO"

echo "=== setup: gddp-config ==="

# 1. Python (for YAML validation)
python3 --version 2>&1 || { echo "✗ python3 not found"; exit 1; }
echo "✓ python3 $(python3 --version 2>&1 | awk '{print $2}')"

# 2. Verify structure
for d in rules schemas templates workflows graphs; do
  [ -d "$d" ] && echo "✓ $d/ present" || echo "⚠ $d/ missing"
done

# 3. YAML lint (just syntax check)
python3 -c "
import yaml, sys, pathlib
ok = 0
for f in pathlib.Path('rules').glob('*.yml'):
    try:
        yaml.safe_load(f.read_text())
        ok += 1
    except Exception as e:
        print(f'✗ {f}: {e}')
if ok: print(f'✓ {ok} rule files parse OK')
" 2>/dev/null || echo "⚠ YAML validation skipped (no yaml module or no rules)"

# 4. Snapshot
echo "--- snapshot ---"
echo "  branch:  $(git branch --show-current 2>/dev/null || echo 'not a git repo')"
echo "  setup:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
