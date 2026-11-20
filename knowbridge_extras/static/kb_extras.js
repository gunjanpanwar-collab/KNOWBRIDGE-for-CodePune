/* KnowBridge extras. Add to any page:  <script src="/kb-extras/kb_extras.js" defer></script>
   - If the page has <div id="kb-dashboard">, renders dashboard + next steps there.
   - Always adds a floating "Ask KnowBridge" chat. All text is inserted with textContent (no XSS). */
(function () {
  const css = `
  .kb-card{background:#fff;border:1px solid #d9e0e3;border-radius:8px;padding:16px;margin:16px 0}
  .kb-counts{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:16px 0}
  .kb-count{background:#fff;border:1px solid #d9e0e3;border-radius:8px;padding:12px}
  .kb-count b{display:block;font-size:26px;font-family:Georgia,serif}
  .kb-count.blocked b,.kb-count.overdue b{color:#b42318}.kb-count.completed b{color:#0f766e}
  .kb-table{width:100%;border-collapse:collapse;font-size:14px}
  .kb-table th,.kb-table td{text-align:left;padding:6px 8px;border-bottom:1px solid #eef1f2;vertical-align:top}
  .kb-tag{display:inline-block;border:1px solid #cbd5da;border-radius:4px;padding:0 6px;font-size:12px;margin-right:4px}
  .kb-tag.overdue{border-color:#b42318;color:#b42318}.kb-tag.due-soon{border-color:#b54708;color:#b54708}
  #kb-fab{position:fixed;right:20px;bottom:20px;z-index:9999;background:#0f766e;color:#fff;border:0;border-radius:24px;padding:12px 18px;font:600 15px system-ui;cursor:pointer}
  #kb-chat{position:fixed;right:20px;bottom:76px;z-index:9999;width:min(380px,calc(100vw - 40px));height:min(520px,70vh);background:#fff;border:1px solid #cbd5da;border-radius:10px;display:none;flex-direction:column;box-shadow:0 8px 30px rgba(0,0,0,.18);font:14px/1.5 system-ui}
  #kb-chat.open{display:flex}
  #kb-log{flex:1;overflow:auto;padding:12px}
  .kb-msg{margin:0 0 10px;white-space:pre-wrap}.kb-msg.me{text-align:right;color:#0f766e}
  .kb-src{font-size:12px;color:#5b6b75;margin:2px 0 10px}
  #kb-form{display:flex;border-top:1px solid #d9e0e3}
  #kb-form input{flex:1;border:0;padding:12px;font:inherit;outline:none}
  #kb-form button{border:0;background:#0f766e;color:#fff;padding:0 16px;cursor:pointer}
  `;
  const style = document.createElement("style"); style.textContent = css; document.head.appendChild(style);

  function el(tag, props, ...kids) {
    const e = document.createElement(tag);
    Object.entries(props || {}).forEach(([k, v]) => (k === "class" ? (e.className = v) : e.setAttribute(k, v)));
    kids.flat().forEach((k) => e.append(k));
    return e;
  }
  const link = (s) => el("a", { href: s.url, target: "_blank", rel: "noopener" }, s.name);
  async function getJSON(url, opts) {
    const r = await fetch(url, Object.assign({ credentials: "same-origin" }, opts));
    if (!r.ok) { const e = new Error("Request failed (" + r.status + ")"); e.status = r.status; throw e; }
    return r.json();
  }

  /* ---------- dashboard ---------- */
  function taskTable(rows, empty) {
    if (!rows.length) return el("p", { class: "muted" }, empty);
    const t = el("table", { class: "kb-table" }, el("tr", {}, ...["Task", "Owner", "Due", "Source"].map((h) => el("th", {}, h))));
    rows.forEach((r) => t.append(el("tr", {},
      el("td", {}, r.title + (r.blocked_by ? " (blocked by " + r.blocked_by + ")" : "")),
      el("td", {}, r.owner || "Unassigned"), el("td", {}, r.due || "-"),
      el("td", {}, link({ name: r.source, url: "/kb/source/" + encodeURIComponent(r.source) })))));
    return t;
  }
  async function renderDashboard(root) {
    root.textContent = "Loading...";
    try {
      const [d, rec] = await Promise.all([getJSON("/api/extras/dashboard" + location.search), getJSON("/api/extras/recommendations" + location.search)]);
      root.textContent = "";
      const c = d.counts;
      root.append(el("div", { class: "kb-counts" }, ...[["completed", "Completed"], ["pending", "Pending"], ["blocked", "Blocked"], ["overdue", "Overdue"]]
        .map(([k, label]) => el("div", { class: "kb-count " + k }, el("b", {}, String(c[k])), label))));
      const next = el("div", { class: "kb-card" }, el("h2", {}, "Suggested next steps"));
      if (!rec.recommendations.length) next.append(el("p", { class: "muted" }, "Nothing urgent. No blocked, overdue or unowned work found."));
      rec.recommendations.forEach((r) => {
        const box = el("div", { style: "margin:0 0 14px" }, el("strong", {}, r.action), el("div", { class: "muted" }, r.why),
          el("div", { class: "kb-src" }, "Source: ", ...r.evidence.map(link)));
        r.context.forEach((cx) => box.append(el("div", { class: "kb-src" }, "Verified note: " + cx.text + " ", ...cx.sources.map(link))));
        next.append(box);
      });
      root.append(next);
      const dl = el("div", { class: "kb-card" }, el("h2", {}, "Deadlines"));
      if (!d.deadlines.length) dl.append(el("p", { class: "muted" }, "No open tasks have a deadline."));
      else {
        const t = el("table", { class: "kb-table" });
        d.deadlines.forEach((x) => t.append(el("tr", {}, el("td", {}, x.due), el("td", {}, el("span", { class: "kb-tag " + x.bucket.replace(" ", "-") }, x.bucket)), el("td", {}, x.title), el("td", {}, x.owner || "Unassigned"))));
        dl.append(t);
      }
      root.append(dl);
      [["blocked", "Blocked", "Nothing is blocked."], ["pending", "Pending", "Nothing is pending."], ["completed", "Completed", "Nothing completed yet."]]
        .forEach(([k, title, empty]) => root.append(el("div", { class: "kb-card" }, el("h2", {}, title + " (" + d[k].length + ")"), taskTable(d[k], empty))));
      d.warnings.forEach((w) => root.append(el("p", { class: "muted" }, w)));
    } catch (e) { root.textContent = e.status === 401 ? "Sign in on the main page first, then reopen this dashboard." : "Could not load the dashboard. " + e.message; }
  }

  /* ---------- chat ---------- */
  function addChat() {
    const log = el("div", { id: "kb-log", "aria-live": "polite" });
    const input = el("input", { type: "text", placeholder: "Ask about the project", "aria-label": "Your question", maxlength: "500" });
    const form = el("form", { id: "kb-form" }, input, el("button", { type: "submit" }, "Ask"));
    const head = el("div", { style: "padding:8px 12px;border-bottom:1px solid #d9e0e3;font-size:13px" }, el("a", { href: "/dashboard", target: "_blank" }, "Open project dashboard"));
    const box = el("div", { id: "kb-chat", role: "dialog", "aria-label": "Ask KnowBridge" }, head, log, form);
    const fab = el("button", { id: "kb-fab", type: "button" }, "Ask KnowBridge");
    fab.onclick = () => box.classList.toggle("open");
    log.append(el("p", { class: "kb-msg" }, "Ask me about decisions, owners, blockers or deadlines. I only answer from approved project information, and I link my sources."));
    form.onsubmit = async (ev) => {
      ev.preventDefault();
      const q = input.value.trim(); if (!q) return;
      input.value = ""; log.append(el("p", { class: "kb-msg me" }, q));
      const wait = el("p", { class: "kb-msg" }, "Checking the record..."); log.append(wait);
      try {
        const r = await getJSON("/api/extras/chat" + location.search, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: q }) });
        wait.textContent = r.answer;
        r.citations.forEach((c) => log.append(el("div", { class: "kb-src" }, "[" + c.n + "] ", ...c.sources.map((s) => [link(s), " "]))));
        if (r.links.length) log.append(el("div", { class: "kb-src" }, "Task sources: ", ...r.links.map((s) => [link(s), " "])));
      } catch (e) { wait.textContent = e.status === 401 ? "Sign in first, then ask again." : "Something went wrong. Try again."; }
      log.scrollTop = log.scrollHeight;
    };
    document.body.append(box, fab);
  }

  function boot() {
    const root = document.getElementById("kb-dashboard");
    if (root) renderDashboard(root);
    addChat();
  }
  document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", boot) : boot();
})();
