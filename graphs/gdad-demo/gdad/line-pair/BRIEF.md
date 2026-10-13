# line-pair

## Goal

Two workers write hello.txt. Acceptance is exactly two non-empty lines.

## Scope

Only hello-a.txt, hello-b.txt, hello.txt, and workers.done under this run's artifacts directory. The workflow concatenates the two worker files into hello.txt.

## Acceptance

hello.txt exists and has exactly two non-empty lines.

## Constraints

No other files. No graph YAML edits.

## Sab's words

Workers write three lines on the first run so the reviewer rejects, then two lines after a redispatch so the reviewer accepts.
