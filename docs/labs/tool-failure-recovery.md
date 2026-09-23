---
hide:
  - toc
---

# Tool failure and recovery lab

Change the failure and recovery policy. The timeline shows which component acts, whether work is retried, and how many external effects remain. Predict the outcome first; then inspect why it happened.

<div class="failure-lab" data-failure-lab>
  <div class="failure-lab__controls" aria-label="Lab controls">
    <label><span>Injected failure</span><select data-lab-failure><option value="malformed_arguments">Malformed tool arguments</option><option value="unknown_tool">Unknown tool name</option><option value="rate_limit">Provider rate limit (429)</option><option value="bad_request">Provider bad request (400)</option><option value="timeout_after_effect" selected>Timeout after the tool committed</option></select></label>
    <label><span>Retry budget: <strong data-lab-retry-value>1</strong></span><input data-lab-retries type="range" min="0" max="3" value="1"></label>
    <label class="failure-lab__check"><input data-lab-key type="checkbox" checked><span>Reuse one operation key</span></label>
    <label class="failure-lab__check"><input data-lab-reconcile type="checkbox" checked><span>Verify independent effect state</span></label>
  </div>
  <div class="failure-lab__prediction">
    <span>Before revealing the run, what do you expect?</span>
    <div><button type="button" data-lab-predict="recovered">Recovers safely</button><button type="button" data-lab-predict="bounded">Stops safely</button><button type="button" data-lab-predict="duplicate">Duplicates work</button></div>
  </div>
  <div class="failure-lab__result" data-lab-result hidden aria-live="polite">
    <div class="failure-lab__summary"><div><span>Outcome</span><strong data-lab-outcome></strong></div><div><span>Attempts</span><strong data-lab-attempts></strong></div><div><span>Effects</span><strong data-lab-effects></strong></div></div>
    <ol class="failure-lab__timeline" data-lab-timeline></ol>
    <p class="failure-lab__lesson" data-lab-lesson></p>
    <p class="failure-lab__prediction-result" data-lab-prediction-result></p>
  </div>
</div>

## Read the result as a harness contract

- **Malformed calls and unknown tools** belong on the model/tool boundary. Validate before dispatch, then return a correlated structured error so the model can correct the call.
- **429 and timeout failures** may be retried, but attempts must share one total deadline and a bounded budget.
- **400 failures** are invalid requests. Repetition amplifies load without changing the request.
- **A timeout after commit** creates an unknown outcome. A stable operation key prevents a second effect; independent reconciliation tells you what actually happened.

The interactive timeline is a deterministic simulation. It explains the policy but does not test a provider or framework.

## Produce the same run record locally

```bash
python -m examples.harness.failure_lab --failure timeout_after_effect --retries 1 --stable-key --reconcile
```

The command emits versioned JSON with the selected policy, timeline, attempt count, effect count, and outcome. Try the unsafe variant:

```bash
python -m examples.harness.failure_lab --failure timeout_after_effect --retries 1 --no-stable-key --no-reconcile
```

Then run the process-crash fixture. It commits a synthetic booking, exits before checkpointing, restarts in a fresh interpreter, and proves through an independent SQLite sink that only one effect exists:

```bash
python -m examples.harness.reliability
pytest tests/test_failure_lab.py tests/test_learning_reliability.py -q
```

## Compare framework behavior separately

The repository's `resilience` arena injects identical malformed model/tool calls into each adapter. That experiment measures whether the framework returns the error to the model and reaches the correction turn:

```bash
python -m arena run --arena resilience --framework all --mode mock --no-scorecard
python .github/scripts/check_resilience.py
```

Mock-mode differences are meaningful for this controlled recovery path because every adapter receives the same scripted fault. They still do not establish live-model quality. Read the [published findings](../findings.md#2-what-breaks-when-the-model-misbehaves) and [run-mode boundaries](../reference/run-modes.md).

## Carry the contract into your harness

Record one terminal result per accepted tool call, stable operation identity for retryable effects, one total deadline, explicit retry classification, and an independent effect oracle. If any of these are missing, make the missing guarantee visible rather than inferring success from the final answer.

Next: [Reliability and restart](../build/reliability.md) · [Lost tool errors](../problems/tool-errors.md) · [Retry amplification](../problems/retry-amplification.md)
