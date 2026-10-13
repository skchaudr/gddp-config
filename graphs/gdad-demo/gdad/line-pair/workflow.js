const read = await shell("cat \"$GDAD_PROMPT_FILE\"");
const text = read.stdout;
await shell("python3 -m gdad_run wait-running \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await parallel("workers", {
  a: () => agent(text + "\nYou are worker A. Write only hello-a.txt in the artifacts directory."),
  b: () => agent(text + "\nYou are worker B. Write only hello-b.txt in the artifacts directory."),
});
await shell("cat \"$GDAD_ARTIFACTS\"/hello-a.txt \"$GDAD_ARTIFACTS\"/hello-b.txt > \"$GDAD_ARTIFACTS\"/hello.txt && date -u +%Y-%m-%dT%H:%M:%SZ > \"$GDAD_ARTIFACTS\"/workers.done");
await shell("python3 -m gdad_run pause-packet \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await checkpoint({ name: "after-workers", prompt: "Workers finished. Resume to review." });
await shell("python3 -m gdad_run mark-resumed \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
await shell("python3 -m gdad_run review \"$GDAD_PROJECT\" \"$GDAD_NODE\"");
