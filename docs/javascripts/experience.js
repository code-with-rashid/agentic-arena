(() => {
  const routes = {
    learn: { title: "See the whole system before learning its parts", body: "Build a mental model of the model, harness, tools, state, boundaries, and environment.", href: "learn/", label: "Open the learning path" },
    build: { title: "Build a minimal harness, then make it dependable", body: "Start with one executable tool loop and add context, protocols, restart safety, evaluation, and isolation deliberately.", href: "build/", label: "Open the build path" },
    compare: { title: "Start with the claim, then inspect the evidence", body: "See measured findings first, check the methodology, and only then apply the decision guide to your constraints.", href: "compare/", label: "Open the comparison room" },
    solve: { title: "Name the failure before choosing a framework fix", body: "Use the problem register for context growth, tool errors, retries, approvals, restarts, and delegation cost.", href: "problems/", label: "Open the problem register" },
  };

  function initPathPicker() {
    const picker = document.querySelector("[data-path-picker]");
    if (!picker) return;
    const result = picker.querySelector("[data-path-result]");
    const buttons = [...picker.querySelectorAll("[data-path]")];
    const render = (key) => {
      const route = routes[key];
      if (!route) return;
      buttons.forEach((button) => button.setAttribute("aria-selected", String(button.dataset.path === key)));
      result.innerHTML = `<span class="path-picker__step">Recommended first step</span><h3>${route.title}</h3><p>${route.body}</p><a href="${route.href}">${route.label} <span aria-hidden="true">→</span></a>`;
      try { localStorage.setItem("arena-path", key); } catch (_) { /* private browsing */ }
    };
    buttons.forEach((button) => button.addEventListener("click", () => render(button.dataset.path)));
    let saved = "learn";
    try { saved = localStorage.getItem("arena-path") || "learn"; } catch (_) { /* private browsing */ }
    render(saved);
  }

  function initLearningProgress() {
    const checkboxes = [...document.querySelectorAll("[data-progress-id]")];
    if (!checkboxes.length) return;
    const count = document.querySelector("[data-progress-count]");
    const bar = document.querySelector("[data-progress-bar]");
    let completed = [];
    try { completed = JSON.parse(localStorage.getItem("arena-learning-progress") || "[]"); } catch (_) { completed = []; }
    const update = () => {
      const selected = checkboxes.filter((box) => box.checked).map((box) => box.dataset.progressId);
      if (count) count.textContent = `${selected.length} of ${checkboxes.length} complete`;
      if (bar) bar.style.width = `${(selected.length / checkboxes.length) * 100}%`;
      try { localStorage.setItem("arena-learning-progress", JSON.stringify(selected)); } catch (_) { /* private browsing */ }
    };
    checkboxes.forEach((box) => { box.checked = completed.includes(box.dataset.progressId); box.addEventListener("change", update); });
    update();
  }

  const failureCatalog = {
    malformed_arguments: { label: "Malformed tool arguments", kind: "model", retryable: false, effect: "none" },
    unknown_tool: { label: "Unknown tool name", kind: "model", retryable: false, effect: "none" },
    rate_limit: { label: "Provider rate limit (429)", kind: "transport", retryable: true, effect: "none" },
    bad_request: { label: "Provider bad request (400)", kind: "transport", retryable: false, effect: "none" },
    timeout_after_effect: { label: "Timeout after the tool committed", kind: "effect", retryable: true, effect: "committed" },
  };

  function simulateFailure({ failure, retries, stableKey, reconcile }) {
    const fault = failureCatalog[failure];
    const timeline = [{ actor: "model", state: "proposed", detail: "The model proposes a tool call." }];
    let attempts = 1;
    let effects = fault.effect === "committed" ? 1 : 0;
    let outcome;
    let lesson;

    if (fault.kind === "model") {
      timeline.push({ actor: "harness", state: "rejected", detail: `Validate and surface: ${fault.label}.` });
      timeline.push({ actor: "model", state: "corrected", detail: "A structured tool error enables a corrected call." });
      timeline.push({ actor: "tool", state: "applied", detail: "The corrected call executes once." });
      effects = 1;
      outcome = "Recovered";
      lesson = "Return one structured result for every accepted call, including failures.";
    } else if (!fault.retryable) {
      timeline.push({ actor: "provider", state: "failed", detail: `${fault.label} is not retryable.` });
      timeline.push({ actor: "harness", state: "stopped", detail: "The harness fails loudly without amplification." });
      outcome = "Failed safely";
      lesson = "Classify failures before retrying; invalid requests do not improve with repetition.";
    } else if (retries === 0) {
      timeline.push({ actor: "provider", state: "failed", detail: fault.label });
      timeline.push({ actor: "harness", state: "stopped", detail: "The retry budget is exhausted." });
      outcome = "Failed within budget";
      lesson = "A bounded failure is observable and preferable to an unbounded retry loop.";
    } else if (fault.kind === "transport") {
      timeline.push({ actor: "provider", state: "failed", detail: "429 received; the first attempt has no effect." });
      attempts += 1;
      timeline.push({ actor: "harness", state: "retried", detail: "Retry once within the shared task deadline." });
      timeline.push({ actor: "provider", state: "succeeded", detail: "The retry succeeds." });
      outcome = "Recovered";
      lesson = "Retry transient transport failures inside a total deadline and attempt budget.";
    } else if (stableKey) {
      timeline.push({ actor: "tool", state: "unknown", detail: "The effect committed, but its acknowledgement was lost." });
      attempts += 1;
      timeline.push({ actor: "harness", state: "retried", detail: "Retry with the same operation key." });
      timeline.push({ actor: "tool", state: "replayed", detail: "The sink returns the original result without another effect." });
      if (reconcile) timeline.push({ actor: "harness", state: "verified", detail: "Independent effect state confirms one commit." });
      outcome = "Recovered without duplication";
      lesson = "Stable operation identity closes the retry window; reconciliation verifies the result.";
    } else {
      timeline.push({ actor: "tool", state: "unknown", detail: "The effect committed, but its acknowledgement was lost." });
      attempts += 1;
      effects += 1;
      timeline.push({ actor: "harness", state: "retried", detail: "A new operation key is generated for the retry." });
      timeline.push({ actor: "tool", state: "duplicated", detail: "The sink accepts a second effect." });
      if (reconcile) {
        timeline.push({ actor: "harness", state: "detected", detail: "Independent state exposes the duplicate." });
        outcome = "Duplicate detected";
        lesson = "Reconciliation detects damage, but a stable key prevents it.";
      } else {
        outcome = "Silent duplicate";
        lesson = "A successful response does not prove the intended effect happened exactly once.";
      }
    }
    return { outcome, attempts, effects, timeline, lesson };
  }

  function initFailureLab() {
    const lab = document.querySelector("[data-failure-lab]");
    if (!lab || lab.dataset.initialized === "true") return;
    lab.dataset.initialized = "true";
    const failure = lab.querySelector("[data-lab-failure]");
    const retries = lab.querySelector("[data-lab-retries]");
    const retryValue = lab.querySelector("[data-lab-retry-value]");
    const stableKey = lab.querySelector("[data-lab-key]");
    const reconcile = lab.querySelector("[data-lab-reconcile]");
    const result = lab.querySelector("[data-lab-result]");
    const predictionResult = lab.querySelector("[data-lab-prediction-result]");
    let prediction = null;

    const expectedPrediction = (run) => {
      if (run.effects > 1) return "duplicate";
      if (run.outcome.toLowerCase().startsWith("failed")) return "bounded";
      return "recovered";
    };
    const render = () => {
      retryValue.textContent = retries.value;
      if (!prediction) {
        result.hidden = true;
        return;
      }
      const run = simulateFailure({ failure: failure.value, retries: Number(retries.value), stableKey: stableKey.checked, reconcile: reconcile.checked });
      lab.querySelector("[data-lab-outcome]").textContent = run.outcome;
      lab.querySelector("[data-lab-attempts]").textContent = run.attempts;
      lab.querySelector("[data-lab-effects]").textContent = run.effects;
      lab.querySelector("[data-lab-lesson]").textContent = run.lesson;
      lab.querySelector("[data-lab-timeline]").innerHTML = run.timeline.map((step, index) => `<li><span>${index + 1}</span><div><strong>${step.actor} · ${step.state}</strong><p>${step.detail}</p></div></li>`).join("");
      predictionResult.textContent = prediction === expectedPrediction(run) ? "Your prediction matched the run." : `Your prediction differed. The run ${run.outcome.toLowerCase()}. Follow the timeline to find the decision point.`;
      result.hidden = false;
    };
    const resetPrediction = () => {
      prediction = null;
      result.hidden = true;
      [...lab.querySelectorAll("[data-lab-predict]")].forEach((button) => button.setAttribute("aria-pressed", "false"));
      retryValue.textContent = retries.value;
    };
    [failure, retries, stableKey, reconcile].forEach((control) => control.addEventListener("input", resetPrediction));
    lab.querySelectorAll("[data-lab-predict]").forEach((button) => button.addEventListener("click", () => {
      prediction = button.dataset.labPredict;
      lab.querySelectorAll("[data-lab-predict]").forEach((peer) => peer.setAttribute("aria-pressed", String(peer === button)));
      render();
    }));
    retryValue.textContent = retries.value;
  }

  const init = () => { initPathPicker(); initLearningProgress(); initFailureLab(); };
  document.addEventListener("DOMContentLoaded", init);
  if (typeof document$ !== "undefined") document$.subscribe(init);
})();
