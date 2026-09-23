# Aider: adjacent baseline

Aider is an open-source terminal pair programmer with deep Git integration. It
uses selected files plus a token-bounded repository map, applies model output
through explicit edit formats, runs lint/tests, and normally commits its edits.

**Evidence status:** source-reviewed on 2026-09-23 at `5dc9490`; latest tagged
release checked as `v0.86.0`. Agentic Arena has not run it locally.

- [Official repository](https://github.com/Aider-AI/aider)
- [Documentation](https://aider.chat/docs/)
- [Repository map](https://aider.chat/docs/repomap.html)
- [Git integration](https://aider.chat/docs/git.html)

## Why it is adjacent

Aider provides CLI and Python scripting, but its reviewed product center is a
human-guided editing session rather than a general remote agent runtime. It
does not expose the same breadth of permission, extension, delegation, and
session-lifecycle contracts as the primary cohort.

That narrower scope makes it valuable. Its repository map selects symbol and
dependency context within a budget. Edit formats make the model-to-patch
boundary explicit. Git commits and `/undo` give the user a familiar audit and
recovery surface.

## What Agentic Arena should test

Use Aider as a lower-complexity editing baseline on tasks that need no remote
tools or delegation. Pin auto-commit, dirty-file, lint, test, map-token, and edit
format settings. Score the working tree and tests independently, and count
extra model calls used for commit messages or repair.

Aider teaches us that strong repository context and a constrained edit protocol
can be more useful than a large orchestration surface. Feature counts must not
penalize a tool for intentionally solving a smaller problem.
