# Arena design: `human_in_the_loop`

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

## Notes

- Baseline `vanilla` can emulate this with a two-phase call; that's a useful
  contrast row but should be marked as emulated, not native.
- Harness needs a resume API: `runner.run(item)` may return a `Suspended` result
  the runner feeds back. Small addition to `arena.types`.
