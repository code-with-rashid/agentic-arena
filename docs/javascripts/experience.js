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

  const init = () => { initPathPicker(); initLearningProgress(); };
  document.addEventListener("DOMContentLoaded", init);
  if (typeof document$ !== "undefined") document$.subscribe(init);
})();
