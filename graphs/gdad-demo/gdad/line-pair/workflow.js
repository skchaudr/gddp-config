await shell("python3 -m gdad_run wait-running \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await parallel("workers", {
  a: () => shell("sh \"$GDAD_WORKER_SH\" a"),
  b: () => shell("sh \"$GDAD_WORKER_SH\" b"),
});
await shell("sh \"$GDAD_WORKER_SH\" concat");
await shell("python3 -m gdad_run pause-packet \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await checkpoint({ name: "after-workers", prompt: "Workers finished. Resume to review." });
await shell("python3 -m gdad_run mark-resumed \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await shell("python3 -m gdad_run review \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
