#!/bin/sh
# One pi worker. $1 is a or b. agent() in pi-extensible-workflows 6.2.0 calls
# createCodemodeExtension, which pi 0.87.1 does not export, so the worker is a
# separate `pi -p` process inside parallel().
set -eu
role="$1"
file="hello-${role}.txt"
prompt="$(cat "$GDAD_PROMPT_FILE")

You are worker ${role}. Using the write tool, create only ${GDAD_ARTIFACTS}/${file} and no other file. Stop when that file exists."
exec pi -ne --no-session -p --approve "$prompt"
