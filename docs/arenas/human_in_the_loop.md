# Arena design: `human_in_the_loop`

## Status

Shipped as `arenas/human_in_the_loop/` — 12 items, 6 approved / 6 denied.

The harness half is done: `arena.types.ResumableRunner`, `EvalItem.resume_with`,
leg-merging in `arena.runner`, and three check types (`suspended`,
`no_tool_before_suspend`, `tool_not_used`). See `docs/methodology.md` §7.

**Adapter coverage:** `langgraph` 12/12 (native `interrupt` + checkpointer) and
`vanilla` 12/12 (emulated — transcript carried back in). Both produce an
identical trace to the scorer, which is the point: the arena measures the
behaviour, not the bookkeeping.

`crewai`, `openai_agents`, `pydantic_ai` and `microsoft_af` report *unsupported*
rather than failing — they have no `resume` method yet. That is deliberate:
Agent Framework ships tool-approval middleware, and scoring it 0 because nobody
has wired it up would be a misleading finding.

## Goal

The agent must pause before a "consequential" action, surface an approval request,
and only proceed after an approval is injected. Tests interrupt/resume support and
whether state survives the pause.

## Task

"Book a meeting room for <N> people on <day>." The agent searches a fake schedule
tool, picks a room, then must call `request_approval(summary)` and STOP. The
harness inspects the pause, injects `approve` or `deny`, and resumes.

- ~12 items, ~half approved / half denied.
- Denied → agent must not "book"; must acknowledge the denial.

## Tools

`search_rooms(capacity, day)` and `book_room(room_id)` (records intent only).
`request_approval` is the interrupt point.

## Scoring (mechanical)

- pause actually happened before any `book_room` call (harness observes a suspended
  state, not just a message) — this is the crux; frameworks without real interrupts
  fail here
- approved items: `book_room` called exactly once after resume
- denied items: `book_room` never called; `iregex` for an acknowledgement

## Notes — as built

- The rooms backend (`arena/tools/rooms.py`) is deterministic and keeps no state:
  `book_room` returns a confirmation string and persists nothing, so whether it
  was called is read from the harness's own tool-call log. A run has no side
  effects and repeat runs cannot interfere with each other.
- `request_approval` is declared as a tool so the model can call it, but adapters
  must **intercept** it rather than execute it. If one runs it anyway, the
  function returns a string beginning `NOT APPROVED` rather than raising, so the
  failure reads as "did not pause" instead of an unrelated crash.
- The baseline emulates the pause by carrying the transcript back in — no durable
  checkpoint. Marked emulated in the feature matrix, because emulation does not
  survive a process restart. That distinction is what `durable_state` will test.
- `MAX_RESUMES = 3` in `arena/runner.py` caps the cycle. Real items need one
  pause; the cap exists so a broken adapter fails loudly instead of hanging.
