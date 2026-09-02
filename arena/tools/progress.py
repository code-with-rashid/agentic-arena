"""The checkpoint interrupt point for the `durable_state` arena.

Like `request_approval`, this is not an ordinary tool: an adapter is expected to
intercept the call and suspend rather than execute it. Reaching this body means
the adapter ran straight through a checkpoint it was supposed to stop at, so it
returns a string the scorer will expose rather than raising, which would look
like an unrelated crash.
"""

from __future__ import annotations


def save_progress(note: str) -> str:
    return f"NOT CHECKPOINTED - the adapter did not suspend at: {note}"
