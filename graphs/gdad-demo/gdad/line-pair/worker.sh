#!/bin/sh
# One pi worker, or the concat step. agent() in pi-extensible-workflows 6.2.0
# calls createCodemodeExtension, which pi 0.87.1 does not export, so each
# worker is a separate `pi -p` inside parallel().
set -eu
role="$1"
if [ "$role" = "concat" ]; then
  python3 - << 'PY'
import os
from datetime import datetime, timezone
from pathlib import Path
art = Path(os.environ["GDAD_ARTIFACTS"])
lines = []
for name in ("hello-a.txt", "hello-b.txt"):
    lines.extend(ln for ln in (art / name).read_text().splitlines() if ln.strip())
(art / "hello.txt").write_text("\n".join(lines) + "\n")
(art / "workers.done").write_text(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n")
PY
  exit 0
fi
file="hello-${role}.txt"
prompt="$(cat "$GDAD_PROMPT_FILE")

You are worker ${role}. Using the write tool, create only ${GDAD_ARTIFACTS}/${file} and no other file. Stop when that file exists."
exec pi -ne --no-session -p --approve "$prompt"
