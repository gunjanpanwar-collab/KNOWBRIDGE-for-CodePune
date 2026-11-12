// KNOWBRIDGE front end. All data comes from the Flask API; permissions are enforced on the server.
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const LABEL = {verified:'Verified', inferred:'Inferred', conflicting:'Conflicting', missing:'Missing'};
const ROLE = {reviewer:'Reviewer', developer:'Incoming developer', member:'Incoming non-technical member'};
let me = null, claims = [], sel = null, tab = 0;

async function api(path, opts = {}) {
  const init = {credentials: 'same-origin', ...opts};
  if (opts.json) { init.method = 'POST'; init.headers = {'Content-Type': 'application/json'}; init.body = JSON.stringify(opts.json); }
  try {
    const r = await fetch(path, init);
    const data = await r.json().catch(() => ({}));
    return {ok: r.ok, status: r.status, data};
  } catch (e) { return {ok: false, status: 0, data: {error: 'Could not reach the server. Check your connection and try again.'}}; }
}
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('on'), 2200); }

function tabsFor(role) { return role === 'reviewer' ? ['Sources', 'Review', 'Handover'] : ['Sources', 'Handover']; }
function renderTabs() {
  const nav = $('#tabs'); nav.innerHTML = '';
  if (!me) return;
  tabsFor(me).forEach((name, i) => {
    const b = document.createElement('button');
    b.textContent = name; b.setAttribute('role', 'tab'); b.setAttribute('aria-selected', i === tab);
    b.onclick = () => go(i); nav.append(b);
  });
}
function sectionIds() { return me === 'reviewer' ? ['s0', 's1', 's2'] : ['s0', 's2']; }
async function go(i) {
  tab = i; renderTabs();
  ['s0', 's1', 's2'].forEach(id => $('#' + id).classList.toggle('on', id === sectionIds()[i]));
  const id = sectionIds()[i];
  if (id === 's0') await loadSources();
  if (id === 's1') await loadClaims();
  if (id === 's2') await loadHandover();
  window.scrollTo(0, 0);
}

async function refreshMe() {
  const r = await api('/api/me'); me = r.data.role || null;
  $('#welcome').classList.toggle('hidden', !!me);
  $('#logoutBtn').classList.toggle('hidden', !me);
  $('#who').textContent = me ? 'Signed in as ' + ROLE[me] : '';
    if (me) $('#roleSel').value = me;
  $('#reviewerTools').classList.toggle('hidden', me !== 'reviewer');
  ['s0', 's1', 's2'].forEach(id => $('#' + id).classList.remove('on'));
  renderTabs();
  if (me) go(0);
}
$('#loginBtn').onclick = async () => {
  const r = await api('/api/login', {json: {role: $('#roleSel').value}});
  if (!r.ok) return toast(r.data.error || 'Sign-in failed.');
  tab = 0; refreshMe();
};
$('#logoutBtn').onclick = async () => { await api('/api/logout', {method: 'POST'}); me = null; claims = []; sel = null; $('#extractMsg').innerHTML = ''; refreshMe(); };

// ---------- Sources ----------
async function loadSources() {
  const r = await api('/api/sources');
  if (!r.ok) return toast(r.data.error || 'Could not load sources.');
  const rows = r.data.sources;
  $('#srcTable').innerHTML = '<tr><th>Source</th><th>Size</th><th>Chunks</th><th>Who can open it</th></tr>' +
    (rows.length ? rows.map(s => `<tr><td>${esc(s.filename)}</td><td>${s.size} chars</td><td>${s.chunks}</td><td>${s.roles.map(x => `<span class="chip">${ROLE[x]}</span>`).join(' ')}</td></tr>`).join('')
                 : '<tr><td colspan="4" class="muted">No sources yet. Reviewers can upload files or load the demo data.</td></tr>');
}
$('#uploadBtn').onclick = async () => {
  const f = $('#fileIn').files[0];
  if (!f) return toast('Choose a file first.');
  const fd = new FormData(); fd.append('file', f);
  fd.append('roles', [...document.querySelectorAll('#roleBoxes input:checked')].map(x => x.value).join(','));
  const r = await api('/api/sources', {method: 'POST', body: fd});
  if (!r.ok) return toast(r.data.error || 'Upload failed.');
  $('#fileIn').value = ''; toast('Source uploaded'); loadSources();
};
$('#demoBtn').onclick = async () => {
  if (!confirm('This replaces all current sources and claims with the demo project. Continue?')) return;
  const r = await api('/api/demo-data', {method: 'POST'});
  if (!r.ok) return toast(r.data.error || 'Could not load demo data.');
  $('#extractMsg').innerHTML = ''; toast('Demo data loaded'); loadSources();
};
$('#extractBtn').onclick = async () => {
  const btn = $('#extractBtn'); btn.disabled = true; btn.textContent = 'Extracting…';
  $('#extractMsg').innerHTML = '<p class="note">Reading sources and checking every quote. This can take up to a minute.</p>';
  const r = await api('/api/extract', {method: 'POST'});
  btn.disabled = false; btn.textContent = 'Extract claims';
  if (!r.ok) { $('#extractMsg').innerHTML = `<div class="banner">${esc(r.data.error || 'Extraction failed.')}</div>`; return; }
  const d = r.data;
  const how = d.mode === 'ai' ? 'The AI proposed these claims and code checked each quote.' : 'The live AI was not used for this run.';
  $('#extractMsg').innerHTML = (d.note ? `<div class="banner">${esc(d.note)}</div>` : '') +
    `<div class="banner ok">${how} ${d.verified} verified, ${d.missing} missing-information, ${d.inferred} inferred (quote not found), ${d.dropped} dropped (no evidence). Next, open the Review tab.</div>`;
};

// ---------- Review ----------
async function loadClaims() {
  const r = await api('/api/claims');
  if (!r.ok) return toast(r.data.error || 'Could not load claims.');
  claims = r.data.claims; renderReview();
}
function renderReview() {
  const n = k => claims.filter(c => c.status === k).length;
  $('#sum').innerHTML = claims.length
    ? Object.keys(LABEL).filter(k => n(k)).map(k => `<span class="badge ${k}">${n(k)} ${LABEL[k].toLowerCase()}</span>`).join('') +
      `<span class="badge" style="background:var(--bd)">${claims.filter(c => c.review === 'approved').length} approved of ${claims.length}</span>`
    : '';
  $('#claimList').innerHTML = claims.length ? claims.map(c => `<div class="claim ${c.status} ${c.review === 'rejected' ? 'rej' : ''} ${sel === c.id ? 'sel' : ''}" tabindex="0" data-id="${c.id}">
      <div class="txt">${esc(c.text)}</div>
      <div class="meta"><span class="chip">${esc(c.type)}</span><span class="badge ${c.status}">${LABEL[c.status]}</span>
      <span class="state-${c.review}">${c.review === 'pending' ? 'Needs review' : c.review === 'approved' ? 'Approved' : 'Rejected'}</span></div></div>`).join('')
    : '<div class="card muted">No claims yet. Go to Sources and click Extract claims.</div>';
  document.querySelectorAll('#claimList .claim').forEach(e => {
    const pick = () => { sel = +e.dataset.id; renderReview(); };
    e.onclick = pick; e.onkeydown = ev => { if (ev.key === 'Enter') pick(); };
  });
  renderPanel();
}
function renderPanel() {
  const c = claims.find(x => x.id === sel), p = $('#panel');
  if (!c) { p.innerHTML = '<b>Evidence</b><p class="muted">Select a claim to see the exact quote behind it and who can open each source.</p>'; return; }
  p.innerHTML = `<b>Evidence</b>
    <label class="note" for="ed">Claim text (edit if wrong)</label>
    <textarea id="ed" rows="3">${esc(c.text)}</textarea>
    ${c.evidence.map(e => `<blockquote>“${esc(e.quote)}”</blockquote><div class="note">${e.found ? 'Quote found in' : '<b>Quote NOT found in</b>'} ${esc(e.source)}. Visible to: ${e.roles.map(r => ROLE[r]).join(', ')}</div>`).join('')}
    ${c.status === 'inferred' ? '<p class="note"><b>Inferred:</b> at least one quote could not be found in its source. Check it carefully before approving.</p>' : ''}
    ${c.status === 'missing' ? '<p class="note"><b>Missing:</b> something expected is not recorded in any source. Ask the person who is leaving.</p>' : ''}
    <div class="formrow"><button class="b p" id="bA">Approve</button><button class="b" id="bS">Save edit</button><button class="b" id="bR">Reject</button></div>`;
  const send = async (body, msg) => {
    const r = await api('/api/claims/' + c.id, {json: body});
    if (!r.ok) return toast(r.data.error || 'Could not save.');
    if (msg) toast(msg); await loadClaims();
  };
  $('#bA').onclick = () => send({review: 'approved', text: $('#ed').value});
  $('#bS').onclick = () => send({text: $('#ed').value}, 'Edit saved');
  $('#bR').onclick = () => send({review: 'rejected'});
}
$('#apprAll').onclick = async () => {
  const todo = claims.filter(c => c.status === 'verified' && c.review === 'pending');
  if (!todo.length) return toast('No pending verified claims.');
  for (const c of todo) await api('/api/claims/' + c.id, {json: {review: 'approved'}});
  toast(todo.length + ' verified claims approved'); loadClaims();
};

// ---------- Handover ----------
const GROUPS = [['Decisions', ['Decision']], ['Ownership', ['Owner']], ['Risks and open items', ['Risk', 'Blocker', 'Open question', 'Next action', 'Dependency']], ['Contacts', ['Contact']]];
async function loadHandover() {
  const r = await api('/api/handover');
  if (!r.ok) return toast(r.data.error || 'Could not load the handover.');
  const d = r.data;
  $('#handSub').textContent = 'Showing what the ' + ROLE[d.role] + ' role may see. Only approved claims appear.';
  const h = $('#hand');
  if (!d.claims.length && !d.restricted) { h.innerHTML = '<div class="card"><b>No approved claims yet.</b><p class="muted">The reviewer needs to extract and approve claims first.</p></div>'; return; }
  const list = a => a.length ? `<ol class="plan">${a.map(x => `<li>${esc(x)}</li>`).join('')}</ol>` : '<p class="note">Nothing here yet.</p>';
  let out = `<div class="card"><h2>Your first day</h2>${list(d.plan.day1)}<h2 style="margin-top:12px">Your first week</h2>${list(d.plan.week1)}<p class="note">This plan is built only from the approved claims you are allowed to see.</p></div>`;
  GROUPS.forEach(([title, types]) => {
    const items = d.claims.filter(c => types.includes(c.type)); if (!items.length) return;
    out += `<h3>${title}</h3>` + items.map(c => `<div class="claim ${c.status}" style="cursor:default"><div>${esc(c.text)}</div>
      <div class="meta"><span class="badge ${c.status}">${LABEL[c.status]}</span>${c.evidence.map(e => `<span class="chip">${esc(e.source)}</span>`).join('')}</div>
      <details style="margin-top:6px"><summary class="note">Show evidence</summary>${c.evidence.map(e => `<blockquote>“${esc(e.quote)}”</blockquote>`).join('')}</details></div>`).join('');
  });
  if (d.restricted) out += `<h3>Restricted</h3>` + Array.from({length: d.restricted}, () => '<div class="locked">Restricted item. Ask the reviewer.</div>').join('');
  h.innerHTML = out;
}

refreshMe();
