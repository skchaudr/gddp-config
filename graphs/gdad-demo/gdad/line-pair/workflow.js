await shell("python3 -m gdad_run wait-running \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await parallel("workers", {
  a: () => shell("sh \"$GDAD_WORKER_SH\" a"),
  b: () => shell("sh \"$GDAD_WORKER_SH\" b"),
});
await shell("python3 -c 'import os; from pathlib import Path; art=Path(os.environ[\"GDAD_ARTIFACTS\"]); lines=[]\nfor name in (\"hello-a.txt\",\"hello-b.txt\"):\n p=art/name\n lines += [ln for ln in p.read_text().splitlines() if ln.strip()]\n(art/\"hello.txt\").write_text(\"\\n\".join(lines)+\"\\n\")\n(art/\"workers.done\").write_text(__import__(\"datetime\").datetime.now(__import__(\"datetime\").timezone.utc).strftime(\"%Y-%m-%dT%H:%M:%SZ\")+\"\\n\")'");
await shell("python3 -m gdad_run pause-packet \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await checkpoint({ name: "after-workers", prompt: "Workers finished. Resume to review." });
await shell("python3 -m gdad_run mark-resumed \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await shell("python3 -m gdad_run review \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
