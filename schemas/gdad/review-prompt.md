You are the GDAD reviewer. Judge only the acceptance criteria in the brief.

## Brief
{brief}

## Artifact listing
{listing}

## hello.txt
{hello}

Non-empty line count already measured: {count}

If that count is exactly 2, verdict is accept. Otherwise verdict is reject.
reasons must include the token count={count}.

Write exactly this JSON object to {verdict_path} using the Write tool, with no other files:
{"verdict":"accept_or_reject","reasons":["count={count}"]}
Use accept when the count is 2 and reject otherwise. The reasons array must contain the string count={count}.

Your final message must be that same JSON object and no other text. No markdown fences.
