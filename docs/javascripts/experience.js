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

  const contextFacts = [
    { id: "approval", text: "Never deploy without explicit approval.", required: true },
    { id: "objective", text: "Migrate the checkout service to v3.", required: false },
    { id: "database-old", text: "The target database is orders-primary.", required: false },
    { id: "discussion", text: "The team discussed dashboard colors.", required: false },
    { id: "database-correction", text: "Correction: use orders-green, not orders-primary.", required: true },
    { id: "health", text: "The v3 staging health check passed.", required: false },
    { id: "request", text: "Prepare the migration plan; do not execute it.", required: false },
  ];

  const renderedLength = (fact) => `[${fact.id}] ${fact.text}\n`.length;

  function selectRecent(facts, budget) {
    const selected = [];
    let used = 0;
    [...facts].reverse().forEach((fact) => {
      if (used + renderedLength(fact) <= budget) {
        selected.unshift(fact);
        used += renderedLength(fact);
      }
    });
    return selected;
  }

  function selectProtected(facts, budget) {
    const required = facts.filter((fact) => fact.required);
    let used = required.reduce((sum, fact) => sum + renderedLength(fact), 0);
    if (used > budget) return { selected: [], failure: true };
    const selectedIds = new Set(required.map((fact) => fact.id));
    [...facts].reverse().forEach((fact) => {
      if (!selectedIds.has(fact.id) && used + renderedLength(fact) <= budget) {
        selectedIds.add(fact.id);
        used += renderedLength(fact);
      }
    });
    return { selected: facts.filter((fact) => selectedIds.has(fact.id)), failure: false };
  }

  function simulateContext(policy, budget, query) {
    let selected = [];
    let failure = false;
    let overflow = false;
    if (policy === "full") {
      selected = contextFacts;
      overflow = selected.reduce((sum, fact) => sum + renderedLength(fact), 0) > budget;
    } else if (policy === "recent") {
      selected = selectRecent(contextFacts, budget);
    } else if (policy === "protected") {
      ({ selected, failure } = selectProtected(contextFacts, budget));
    } else if (policy === "retrieval") {
      const candidates = contextFacts.filter((fact) => fact.required || fact.text.toLowerCase().includes(query.toLowerCase()));
      ({ selected, failure } = selectProtected(candidates, budget));
    } else {
      const compacted = [contextFacts[0], contextFacts[4], { id: "summary", text: "Checkout v3 migration planning; staging is healthy; do not execute.", required: false }];
      ({ selected, failure } = selectProtected(compacted, budget));
    }
    const ids = new Set(selected.map((fact) => fact.id));
    const missing = contextFacts.filter((fact) => fact.required && !ids.has(fact.id));
    const used = selected.reduce((sum, fact) => sum + renderedLength(fact), 0);
    let outcome = "Bounded context";
    let lesson = "Required obligations survived and every omission remains visible by source ID.";
    if (failure) {
      outcome = "Failed visibly";
      lesson = "The required obligations do not fit. Increase the budget or shorten them explicitly.";
    } else if (overflow) {
      outcome = "Budget exceeded";
      lesson = "Full replay preserves evidence but does not obey the configured request budget.";
    } else if (missing.length) {
      outcome = "Obligation lost";
      lesson = "A recent window can fit while silently dropping an early approval or correction.";
    } else if (policy === "summary") {
      outcome = "Compacted with provenance loss";
      lesson = "Compaction saves space, but the synthetic summary no longer cites every source it replaced.";
    }
    return { selected, ids, missing, used, outcome, lesson, overflow, failure };
  }

  function initContextLab() {
    const lab = document.querySelector("[data-context-lab]");
    if (!lab || lab.dataset.initialized === "true") return;
    lab.dataset.initialized = "true";
    const policy = lab.querySelector("[data-context-policy]");
    const budget = lab.querySelector("[data-context-budget]");
    const query = lab.querySelector("[data-context-query]");
    const render = () => {
      const limit = Number(budget.value);
      const run = simulateContext(policy.value, limit, query.value);
      lab.querySelector("[data-context-budget-value]").textContent = limit;
      lab.querySelector("[data-context-used]").textContent = `${run.used} / ${limit} characters`;
      lab.querySelector("[data-context-outcome]").textContent = run.outcome;
      lab.querySelector("[data-context-meter]").style.width = `${Math.min(100, (run.used / limit) * 100)}%`;
      lab.querySelector("[data-context-meter]").dataset.overflow = String(run.overflow);
      lab.querySelector("[data-context-text]").textContent = run.selected.length ? run.selected.map((fact) => `[${fact.id}] ${fact.text}`).join("\n") : "No request sent: required evidence exceeds the budget.";
      lab.querySelector("[data-context-lesson]").textContent = run.lesson;
      lab.querySelector("[data-context-sources]").innerHTML = contextFacts.map((fact) => `<li data-selected="${run.ids.has(fact.id)}"><span>${fact.id}${fact.required ? " · required" : ""}</span><p>${fact.text}</p><small>${run.ids.has(fact.id) ? "included" : "omitted"}</small></li>`).join("");
      query.disabled = policy.value !== "retrieval";
    };
    [policy, budget, query].forEach((control) => control.addEventListener("input", render));
    render();
  }

  function simulateApproval({ decision, gated, durable, stable, crash }) {
    const timeline = [{ actor: "model", state: "proposed", detail: "Book room R1 for the requested meeting." }];
    let effects = 0;
    let restarts = 0;
    const record = (outcome) => ({ outcome, effects, restarts, timeline });
    if (!gated) {
      effects = 1;
      timeline.push({ actor: "tool", state: "applied", detail: "Advisory approval allowed the booking to run." });
    }
    timeline.push({ actor: "harness", state: "paused", detail: "The pending operation and approval request are recorded." });
    if (crash === "after_pause") {
      restarts = 1;
      timeline.push({ actor: "process", state: "crashed", detail: "The process exits while approval is pending." });
      if (!durable) {
        timeline.push({ actor: "harness", state: "lost", detail: "In-memory pause state cannot be resumed." });
        return record("Lost pending operation");
      }
      timeline.push({ actor: "harness", state: "restored", detail: "A fresh process loads serializable pause state." });
    }
    timeline.push({ actor: "human", state: decision, detail: `The trusted decision is ${decision}.` });
    if (decision === "deny") {
      if (effects) {
        timeline.push({ actor: "oracle", state: "detected", detail: "The independent sink already contains a booking." });
        return record("Unauthorized effect");
      }
      timeline.push({ actor: "harness", state: "stopped", detail: "The denied operation is never dispatched." });
      return record("Denied safely");
    }
    if (!gated) {
      timeline.push({ actor: "harness", state: "completed", detail: "Approval arrives after the effect already happened." });
      return record("Completed without enforcement");
    }
    effects = 1;
    timeline.push({ actor: "tool", state: "applied", detail: "The approved operation commits once." });
    let outcome = "Approved once";
    if (crash === "after_effect") {
      restarts = 1;
      timeline.push({ actor: "process", state: "crashed", detail: "The acknowledgement is lost before checkpointing." });
      if (!durable) {
        timeline.push({ actor: "harness", state: "lost", detail: "Resume state was not durable." });
        return record("Effect committed; run state lost");
      }
      timeline.push({ actor: "harness", state: "restored", detail: "A fresh process retries the pending operation." });
      if (stable) {
        timeline.push({ actor: "tool", state: "replayed", detail: "The stable operation ID returns the first receipt." });
        outcome = "Resumed without duplication";
      } else {
        effects += 1;
        timeline.push({ actor: "tool", state: "duplicated", detail: "A new operation ID creates a second booking." });
        outcome = "Duplicate after restart";
      }
    }
    timeline.push({ actor: "oracle", state: "verified", detail: `Independent effect count: ${effects}.` });
    return record(outcome);
  }

  function initApprovalLab() {
    const lab = document.querySelector("[data-approval-lab]");
    if (!lab || lab.dataset.initialized === "true") return;
    lab.dataset.initialized = "true";
    const decision = lab.querySelector("[data-approval-decision]");
    const crash = lab.querySelector("[data-approval-crash]");
    const gated = lab.querySelector("[data-approval-gated]");
    const durable = lab.querySelector("[data-approval-durable]");
    const stable = lab.querySelector("[data-approval-stable]");
    const render = () => {
      const run = simulateApproval({ decision: decision.value, crash: crash.value, gated: gated.checked, durable: durable.checked, stable: stable.checked });
      lab.querySelector("[data-approval-outcome]").textContent = run.outcome;
      lab.querySelector("[data-approval-restarts]").textContent = run.restarts;
      lab.querySelector("[data-approval-effects]").textContent = run.effects;
      lab.querySelector("[data-approval-timeline]").innerHTML = run.timeline.map((step, index) => `<li><span>${index + 1}</span><div><strong>${step.actor} · ${step.state}</strong><p>${step.detail}</p></div></li>`).join("");
    };
    [decision, crash, gated, durable, stable].forEach((control) => control.addEventListener("input", render));
    render();
  }

  const copyText = async (value, status, message) => {
    try {
      await navigator.clipboard.writeText(value);
      status.textContent = message;
    } catch (_) {
      status.textContent = "Copy was blocked. Select the record and copy it manually.";
    }
  };

  const downloadRecord = (filename, record) => {
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: "application/json" }));
    link.download = filename;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const setQuery = (values) => {
    const url = new URL(window.location.href);
    Object.entries(values).forEach(([key, value]) => url.searchParams.set(key, String(value)));
    history.replaceState(null, "", url);
    return url.toString();
  };

  function buildHarnessDesign({ workload, risk, restart, approval, delegation }) {
    const components = [
      ["model_port", "Bounded requests and correlated action proposals"],
      ["context_builder", "Select evidence without granting authority"],
      ["scheduler", "Own task, call, action, and deadline budgets"],
      ["tool_dispatcher", "Validate requests and return one result per call"],
      ["executor", "Apply allowed operations in an explicit runtime"],
      ["trace_and_eval", "Record events and check effects independently"],
    ];
    const requirements = new Set(["R1", "R2", "R4", "R7", "R8", "R10"]);
    if (restart !== "stateless") {
      components.push(["checkpoint_store", "Restore serializable run state"]);
      ["R3", "R12"].forEach((item) => requirements.add(item));
    }
    if (approval !== "none" || risk !== "read_only") {
      components.push(["policy_and_approval", "Bind authority to an exact operation"]);
      ["R5", "R9"].forEach((item) => requirements.add(item));
    }
    if (restart === "effect_safe" || risk === "irreversible") {
      components.push(["effect_journal", "Keep stable operation identity and reconcile ambiguity"]);
      ["R6", "R13"].forEach((item) => requirements.add(item));
    }
    if (delegation) {
      components.push(["delegation_supervisor", "Own child budgets, provenance, and cancellation"]);
      requirements.add("R11");
    }
    if (workload === "coding") {
      components.push(["workspace_boundary", "Scope repository reads, writes, commands, and cleanup"]);
      requirements.add("R14");
    }
    const experiments = [
      "Reject malformed and unknown tool calls without losing correlation.",
      "Fail visibly when required context cannot fit the request budget.",
      "Verify allowed and denied effects through an independent sink.",
    ];
    if (restart !== "stateless") experiments.push("Resume in a fresh process from serialized state.");
    if (restart === "effect_safe" || risk === "irreversible") experiments.push("Crash after effect commit and prove replay creates one effect.");
    if (delegation) experiments.push("Cancel a parent during child work and account for the child outcome.");
    return {
      schema: "agentic-arena.harness-design/v1",
      evidence_level: "design-guidance",
      decisions: { workload, effect_risk: risk, restart, approval, delegation },
      components: components.map(([id, responsibility]) => ({ id, responsibility })),
      requirements: [...requirements].sort((a, b) => Number(a.slice(1)) - Number(b.slice(1))),
      acceptance_experiments: experiments,
      boundary: "This record proposes contracts; it does not prove production behavior.",
    };
  }

  function initDesignLab() {
    const lab = document.querySelector("[data-design-lab]");
    if (!lab || lab.dataset.initialized === "true") return;
    lab.dataset.initialized = "true";
    const controls = {
      workload: lab.querySelector("[data-design-workload]"),
      risk: lab.querySelector("[data-design-risk]"),
      restart: lab.querySelector("[data-design-restart]"),
      approval: lab.querySelector("[data-design-approval]"),
      delegation: lab.querySelector("[data-design-delegation]"),
    };
    const status = lab.querySelector("[data-design-action]");
    let record;
    const params = new URLSearchParams(window.location.search);
    Object.entries(controls).forEach(([key, control]) => {
      if (!params.has(key)) return;
      if (control.type === "checkbox") control.checked = params.get(key) === "true";
      else if ([...control.options].some((option) => option.value === params.get(key))) control.value = params.get(key);
    });
    const render = () => {
      const values = {
        workload: controls.workload.value,
        risk: controls.risk.value,
        restart: controls.restart.value,
        approval: controls.approval.value,
        delegation: controls.delegation.checked,
      };
      record = buildHarnessDesign(values);
      lab.querySelector("[data-design-components]").innerHTML = record.components.map((item, index) => `<li><span>${String(index + 1).padStart(2, "0")}</span><div><strong>${item.id.replaceAll("_", " ")}</strong><p>${item.responsibility}</p></div></li>`).join("");
      lab.querySelector("[data-design-record]").textContent = JSON.stringify(record, null, 2);
      lab.querySelector("[data-design-requirements]").textContent = record.requirements.join(" · ");
      lab.querySelector("[data-design-boundary]").textContent = record.boundary;
      setQuery(values);
      status.textContent = "";
    };
    Object.values(controls).forEach((control) => control.addEventListener("input", render));
    lab.querySelector("[data-design-copy]").addEventListener("click", () => copyText(JSON.stringify(record, null, 2), status, "Design record copied."));
    lab.querySelector("[data-design-download]").addEventListener("click", () => { downloadRecord("harness-design-v1.json", record); status.textContent = "Design record downloaded."; });
    lab.querySelector("[data-design-share]").addEventListener("click", () => copyText(window.location.href, status, "Share link copied."));
    render();
  }

  const evidenceClaims = {
    wiring: { modes: ["mock", "offline-fixture", "codex", "live"], question: "Does the path connect and return the expected shape?" },
    recovery: { modes: ["offline-fixture", "codex", "live"], question: "Does the harness preserve the recovery contract under a controlled fault?" },
    real_model: { modes: ["codex", "live"], question: "Can a real model complete the fixed functional path?" },
    provider_comparison: { modes: ["live"], question: "How do repeated native-provider runs compare under shared controls?" },
  };

  function evidenceLimitation(claim, mode, repetitions) {
    if (mode === "mock") return "Fixed responses establish wiring and mechanics, not model capability.";
    if (mode === "offline-fixture") return "The controlled fixture establishes local behavior, not provider performance.";
    if (mode === "codex") return "A translated subscription run is a functional check, not a native benchmark.";
    if (claim === "provider_comparison" && repetitions < 3) return "Native evidence is eligible, but fewer than three repetitions do not describe variability.";
    return "Native evidence can support this claim when shared controls and uncertainty are reported.";
  }

  function makeEvidenceRecord(claim, mode, model, repetitions, dataset, scorer) {
    return {
      schema: "agentic-arena.run-record/v1",
      claim: { id: claim, question: evidenceClaims[claim].question },
      evidence: { mode, supports_claim: evidenceClaims[claim].modes.includes(mode), limitation: evidenceLimitation(claim, mode, repetitions) },
      provenance: { commit: "record-at-run-time", config: "shared", model, dataset, scorer, repetitions, exclusions: [] },
      observations: [],
      design_guidance: [],
    };
  }

  function compareEvidence(left, right) {
    const fields = ["claim", "mode", "dataset", "scorer"];
    if (["real_model", "provider_comparison"].includes(left.claim.id)) fields.push("model");
    const values = {
      claim: [left.claim.id, right.claim.id], mode: [left.evidence.mode, right.evidence.mode],
      dataset: [left.provenance.dataset, right.provenance.dataset], scorer: [left.provenance.scorer, right.provenance.scorer],
      model: [left.provenance.model, right.provenance.model],
    };
    const blocking = fields.filter((field) => values[field][0] !== values[field][1]);
    return {
      schema: "agentic-arena.manifest-comparison/v1",
      comparable: left.evidence.supports_claim && right.evidence.supports_claim && blocking.length === 0,
      matched_fields: fields.filter((field) => !blocking.includes(field)),
      blocking_differences: blocking,
      note: "A comparable contract still needs repeated runs and uncertainty reporting.",
    };
  }

  function initEvidenceLab() {
    const lab = document.querySelector("[data-evidence-lab]");
    if (!lab || lab.dataset.initialized === "true") return;
    lab.dataset.initialized = "true";
    const selectors = ["claim", "dataset", "scorer", "a-mode", "a-model", "a-repetitions", "b-mode", "b-model", "b-repetitions"];
    const controls = Object.fromEntries(selectors.map((name) => [name, lab.querySelector(`[data-evidence-${name}]`)]));
    const status = lab.querySelector("[data-evidence-action]");
    const params = new URLSearchParams(window.location.search);
    selectors.forEach((name) => {
      const control = controls[name];
      if (!params.has(name)) return;
      if (control.tagName === "SELECT" && ![...control.options].some((option) => option.value === params.get(name))) return;
      control.value = params.get(name);
    });
    let envelope;
    const render = () => {
      const claim = controls.claim.value;
      const dataset = controls.dataset.value;
      const scorer = controls.scorer.value;
      const left = makeEvidenceRecord(claim, controls["a-mode"].value, controls["a-model"].value, Math.max(1, Number(controls["a-repetitions"].value)), dataset, scorer);
      const right = makeEvidenceRecord(claim, controls["b-mode"].value, controls["b-model"].value, Math.max(1, Number(controls["b-repetitions"].value)), dataset, scorer);
      const comparison = compareEvidence(left, right);
      envelope = { schema: "agentic-arena.evidence-workspace/v1", records: [left, right], comparison };
      [["a", left], ["b", right]].forEach(([side, record]) => {
        const target = lab.querySelector(`[data-evidence-${side}-support]`);
        target.dataset.supported = String(record.evidence.supports_claim);
        target.innerHTML = `<strong>${record.evidence.supports_claim ? "Supports this claim" : "Cannot support this claim"}</strong><p>${record.evidence.limitation}</p>`;
      });
      lab.querySelector("[data-evidence-verdict]").textContent = comparison.comparable ? "Comparable contract" : "Do not compare directly";
      lab.querySelector("[data-evidence-reason]").textContent = comparison.comparable ? comparison.note : (comparison.blocking_differences.length ? `Blocking differences: ${comparison.blocking_differences.join(", ")}.` : "At least one run uses an evidence mode that cannot support the claim.");
      const fields = ["claim", "mode", "dataset", "scorer", ...(["real_model", "provider_comparison"].includes(claim) ? ["model"] : [])];
      lab.querySelector("[data-evidence-fields]").innerHTML = fields.map((field) => `<li data-matched="${comparison.matched_fields.includes(field)}"><span>${field.replaceAll("_", " ")}</span><strong>${comparison.matched_fields.includes(field) ? "match" : "different"}</strong></li>`).join("");
      lab.querySelector("[data-evidence-record]").textContent = JSON.stringify(envelope, null, 2);
      setQuery(Object.fromEntries(selectors.map((name) => [name, controls[name].value])));
      status.textContent = "";
    };
    Object.values(controls).forEach((control) => control.addEventListener("input", render));
    lab.querySelector("[data-evidence-copy]").addEventListener("click", () => copyText(JSON.stringify(envelope, null, 2), status, "Evidence records copied."));
    lab.querySelector("[data-evidence-download]").addEventListener("click", () => { downloadRecord("evidence-workspace-v1.json", envelope); status.textContent = "Evidence records downloaded."; });
    lab.querySelector("[data-evidence-share]").addEventListener("click", () => copyText(window.location.href, status, "Share link copied."));
    render();
  }

  const init = () => { initPathPicker(); initLearningProgress(); initFailureLab(); initContextLab(); initApprovalLab(); initDesignLab(); initEvidenceLab(); };
  document.addEventListener("DOMContentLoaded", init);
  if (typeof document$ !== "undefined") document$.subscribe(init);
})();
