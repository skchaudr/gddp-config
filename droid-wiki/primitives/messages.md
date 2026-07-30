# Messages

Messages are short, structured coordination payloads exchanged between agents in a harness session (for example IRC-style `send` / `inbox` between subagents). They are not persisted graph truth and are not defined in `schemas/v1/`; they exist only for live multi-agent workflows.

## Role in the pipeline

Unlike [events](event.md) (durable, normalized webhook facts) or [jobs](job.md) (bounded work records), messages are ephemeral steering: status, handoffs, and clarifications. The runtime graph engine does not route on message content.

## Conventions

Keep message bodies plain prose; reference large artifacts via `local://` or `artifact://` URIs instead of inlining blobs. Reply with `replyTo` when answering a peer question.

## Related pages

- [Primitives index](index.md)
- [Event](event.md)
- [Job](job.md)