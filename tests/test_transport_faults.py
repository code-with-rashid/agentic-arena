"""What happens when the *gateway* misbehaves, rather than the model?

The `resilience` arena scripts the model doing something unreasonable. Nothing
measured what happens when the provider returns 429, 500, or 400 — which is what
real deployments actually hit, and which is handled by a layer none of the arenas
touch.

Measured against a mock that fails a fixed number of attempts and then serves
normally:

    framework       429 once      429 x3                500 once    400
    ----------------------------------------------------------------------
    vanilla         RAISES (1)    raises (1)            RAISES (1)  raises (1)
    langgraph       ok (2)        raises (2)            ok (2)      raises (1)
    pydantic_ai     ok (2)        raises (3)            ok (2)      raises (1)
    openai_agents   ok (2)        raises (3)            ok (2)      raises (1)
    microsoft_af    ok (2)        raises (3)            ok (2)      raises (1)
    google_adk      ok (2)        raises (3)            ok (2)      raises (1)
    smolagents      ok (2)        ok (4, +2-4 min)      ok (2)      raises (1)

(attempts in brackets; backoff between the first retries is ~0.5s then ~0.8s)

Three findings.

**This is the clearest answer yet to "what does a framework buy you?"** The
hand-rolled stdlib loop has no retry at all: one 429 and the item is lost. Every
framework survives a transient rate limit. That is a real operational difference
and none of the other arenas can see it, because they never fail a request.

**Five of six retry exactly twice, and LangGraph only once.** It gives up a whole
attempt earlier than everyone else, which on a provider that rate-limits in short
bursts is the difference between a blip and a lost item.

**smolagents keeps going, and blocks for minutes.** It is the only entry that
eventually *succeeds* through three consecutive 429s — after sleeping 139 s, 160 s
and 225 s across three measurements of the same plan. Nothing in the scorecard would show that: the item
passes. In a batch it is a throughput collapse, and it is the opposite trade-off
from everyone else's "fail fast and hand you the error".

**Everyone refuses to retry a 400**, which is correct — a malformed request will
be malformed the second time too.

What is gated here are the invariants: a healthy control answers in one attempt,
nobody retries a 400, and the baseline's lack of retry is pinned so that the
comparison keeps meaning something. Per-framework retry counts are findings and
live in docs/, the same rule as `resilience`.

The three-consecutive-429 column is deliberately **not** gated: reproducing
smolagents' sleep would add two to four minutes to CI to re-measure a number that
is already written down, and being jittered it is not one a test could assert
tightly anyway. Reproduce it with

    python .github/scripts/report_transport.py --deep
"""

import contextlib
from dataclasses import replace

import pytest

from arena.config import ArenaConfig
from arena.llm.mockserver import MockScript, MockServer
from arena.registry import available_frameworks, load_framework
from arena.types import ArenaSpec, EvalItem

STUBS = {"claude_agent_sdk"}
ANSWER = "The Eiffel Tower is 330 metres tall."
SCRIPT = MockScript({"default": {"turns": [{"content": ANSWER}]}})
ITEM = EvalItem(id="t-01", input="How tall is the Eiffel Tower?", checks=[])


def _arena():
    return ArenaSpec(
        id="transport",
        description="transport faults",
        tools=["search"],
        system_prompt_intent="\nAnswer the question concisely.\n",
        dataset=[],
        mock_script_path="",
    )


def _buildable():
    out = []
    for name in available_frameworks():
        if name in STUBS or name.endswith("_multi"):
            continue
        try:
            config = replace(ArenaConfig(mode="mock"), base_url="http://127.0.0.1:1", api_key="k")
            load_framework(name).build(_arena(), config)
        except Exception:  # noqa: BLE001 - not installed in this venv
            continue
        out.append(name)
    return out


BUILDABLE = _buildable()


def _gaps(name, faults, retry_after=None):
    """Seconds between successive attempts — the framework's actual backoff."""
    with MockServer(
        SCRIPT, arena_tools=["search"], faults=faults, retry_after=retry_after
    ) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        with contextlib.suppress(Exception):
            load_framework(name).build(_arena(), config).run(ITEM)
        stamps = server.attempts
        return [b - a for a, b in zip(stamps, stamps[1:], strict=False)]


def _run(name, faults):
    """Run one item against a gateway that fails on `faults`. Returns (outcome, attempts)."""
    with MockServer(SCRIPT, arena_tools=["search"], faults=faults) as server:
        config = replace(
            ArenaConfig(mode="mock"),
            base_url=server.base_url,
            api_key="mock-key",
            max_tool_iterations=6,
        )
        try:
            result = load_framework(name).build(_arena(), config).run(ITEM)
            outcome = "answered" if ANSWER in (result.output_text or "") else "gave up"
        except Exception as exc:  # noqa: BLE001 - the outcome under test
            outcome = f"raised {type(exc).__name__}"
        return outcome, len(server.attempts)


@pytest.mark.parametrize("name", BUILDABLE)
def test_a_healthy_gateway_costs_exactly_one_attempt(name):
    """The control. Without this, a framework that retried constantly would look fine."""
    outcome, attempts = _run(name, [])
    assert outcome == "answered", f"{name}: {outcome} against a healthy gateway"
    assert attempts == 1, f"{name}: made {attempts} attempts with nothing failing"


@pytest.mark.parametrize("name", BUILDABLE)
def test_nobody_retries_a_bad_request(name):
    """A 400 will be a 400 the second time. Retrying it burns quota for nothing.

    The one place every framework here agrees, which is why it is a gate rather
    than a finding: a library that started retrying 400s would be doing something
    unambiguously wrong.
    """
    _, attempts = _run(name, [400, 200])
    assert attempts == 1, f"{name}: retried a 400 ({attempts} attempts)"


@pytest.mark.parametrize("name", BUILDABLE)
def test_a_transient_rate_limit_is_survivable_or_is_reported(name):
    """Either retry through one 429, or fail loudly. Never answer as if nothing happened.

    Deliberately permissive about *which*: `vanilla` raises and every framework
    retries, and both are defensible designs. What would not be defensible is
    returning a confident answer built on a request that never succeeded.
    """
    outcome, attempts = _run(name, [429, 200])
    if outcome == "answered":
        assert attempts >= 2, f"{name}: answered without ever reaching a served request"
    else:
        assert outcome.startswith("raised"), f"{name}: swallowed a 429 as {outcome!r}"


def test_the_stdlib_baseline_has_no_retry_at_all():
    """Pinned, because it is the control the whole comparison rests on.

    If `vanilla` ever grew a retry, "every framework survives a transient rate
    limit and the hand-rolled loop does not" would stop being true, and the
    finding in docs/transport.md would be quietly wrong.
    """
    outcome, attempts = _run("vanilla", [429, 200])
    assert attempts == 1, f"baseline now retries ({attempts} attempts) — update docs/transport.md"
    assert outcome.startswith("raised"), outcome


def test_a_faulted_attempt_consumes_no_scripted_turn():
    """The instrument itself: a 429 never reads the prompt, so it must not advance the script.

    If it did, a framework that retried would be served turn 2 on its retry and
    every measurement above would be comparing different conversations.
    """
    with MockServer(SCRIPT, arena_tools=["search"], faults=[429, 429, 200]) as server:
        config = replace(ArenaConfig(mode="mock"), base_url=server.base_url, api_key="mock-key")
        with contextlib.suppress(Exception):  # the baseline does not retry; it raises
            load_framework("vanilla").build(_arena(), config).run(ITEM)
        assert len(server.attempts) == 1
        assert server.requests == [], "a faulted attempt was recorded as a served request"


RETRY_AFTER_SECONDS = 3


@pytest.mark.parametrize("name", BUILDABLE)
def test_a_framework_that_retries_honours_retry_after(name):
    """If the provider says how long to wait, wait that long.

    Every framework here that retries at all honours the header exactly — the
    measured gap lands within a tenth of a second of what was asked for. That
    uniformity is why this is a gate rather than a finding: a library that
    ignored a server-directed delay would hammer a rate-limited endpoint, and
    that is unambiguous enough to fail CI over.

    `vanilla` never retries, so there is no gap to check and the test passes
    trivially for it — pinned separately by
    `test_the_stdlib_baseline_has_no_retry_at_all`.
    """
    gaps = _gaps(name, [429, 200], retry_after=RETRY_AFTER_SECONDS)
    if not gaps:
        return
    assert abs(gaps[0] - RETRY_AFTER_SECONDS) < 0.5, (
        f"{name}: asked to wait {RETRY_AFTER_SECONDS}s, waited {gaps[0]:.2f}s"
    )


def test_smolagents_stacks_a_second_retry_layer_that_ignores_retry_after():
    """The 2-4 minute stall is an outer retry loop, not the HTTP client.

    Two layers are at work, and only the inner one listens to the provider:

      * the OpenAI client retries twice and honours `Retry-After` (capped at two
        minutes) — visible above, and in the gaps here as two prompt retries;
      * `smolagents.models` then wraps that client in its own `Retrying` with
        `RETRY_MAX_ATTEMPTS = 3`, `RETRY_WAIT = 60`,
        `RETRY_EXPONENTIAL_BASE = 2` and jitter, computing
        `delay *= base * (1 + random())`. The first outer sleep is therefore
        `60 x 2 x (1 + random())` — **120 to 240 seconds** — and nothing in that
        path consults the header.

    So a provider saying "retry in 3 seconds" cannot shorten a wait of minutes.
    Five measurements of that outer sleep landed at 139, 160, 213, 220 and 225
    seconds, all inside the predicted bracket.

    This asserts the *constants*, not the sleep: reproducing it costs two to four
    minutes of wall clock, and `report_transport.py --deep` is there for that.
    Reading them from the installed module is what makes this a real check — if
    upstream lowers `RETRY_WAIT`, this fails and the docs get corrected.
    """
    models = pytest.importorskip("smolagents.models")
    wait = models.RETRY_WAIT
    base = models.RETRY_EXPONENTIAL_BASE
    attempts = models.RETRY_MAX_ATTEMPTS
    low, high = wait * base, wait * base * 2
    assert (low, high) == (120, 240), (
        f"smolagents' outer backoff is now {low}-{high}s (RETRY_WAIT={wait}, "
        f"base={base}) — docs/transport.md quotes 120-240s and needs updating"
    )
    assert attempts > 1, "the outer retry layer is gone; docs/transport.md needs updating"
