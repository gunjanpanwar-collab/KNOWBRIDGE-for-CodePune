/* ==========================================================================
   HandoverTrail prototype
   Demo data only. No live AI: extraction results are pre-filled.
   ========================================================================== */


/* ==========================================================================
   1. DATA
   ========================================================================== */

const ROLES = {
  rev: 'Reviewer',
  dev: 'Incoming developer',
  non: 'Incoming non-technical member',
};

// Which roles may open each source file
const SOURCES = {
  n12:   { name: 'meeting_notes_12.md',          roles: ['rev', 'dev', 'non'] },
  n14:   { name: 'meeting_notes_14.md',          roles: ['rev', 'dev', 'non'] },
  tasks: { name: 'tasks.csv',                    roles: ['rev', 'dev', 'non'] },
  gh:    { name: 'github_export.json',           roles: ['rev', 'dev'] },
  chat:  { name: 'leadership_chat_private.txt',  roles: ['rev'] },
};

const STATUS_LABELS = {
  verified:    'Verified',
  inferred:    'Inferred',
  conflicting: 'Conflicting',
  missing:     'Missing',
  stated:      'Stated by leaver',
};

const REVIEW_LABELS = {
  pending:  'Needs review',
  approved: 'Approved',
  rejected: 'Rejected',
};

// Each claim cites one or more pieces of evidence: { source, quote }
const claims = [
  {
    id: 1,
    type: 'Decision',
    text: 'The team switched from Stripe to Razorpay because Stripe did not support INR.',
    status: 'verified',
    evidence: [
      { source: 'n12', quote: 'Stripe does not support INR payouts for our club account.' },
    ],
  },
  {
    id: 2,
    type: 'Decision',
    text: 'The Razorpay switch deadline is unclear: 30 September in one source, 15 October in two others.',
    status: 'conflicting',
    evidence: [
      { source: 'n12',   quote: 'Deadline for the switch: 30 September.' },
      { source: 'n14',   quote: 'Revised target for the Razorpay switch: 15 October, because of exams.' },
      { source: 'tasks', quote: 'T1,Switch checkout to Razorpay,Karan,In progress,2026-10-15' },
    ],
  },
  {
    id: 3,
    type: 'Owner',
    text: 'Karan owns the Razorpay checkout work.',
    status: 'verified',
    evidence: [
      { source: 'tasks', quote: 'T1,Switch checkout to Razorpay,Karan,In progress' },
    ],
  },
  {
    id: 4,
    type: 'Owner',
    text: 'Meera owns the mobile menu overlap fix.',
    status: 'verified',
    evidence: [
      { source: 'tasks', quote: 'T2,Fix mobile menu overlap,Meera,To do' },
    ],
  },
  {
    id: 5,
    type: 'Blocker',
    text: 'No one owns the confirmation email failure (issue #21).',
    status: 'missing',
    evidence: [
      { source: 'tasks', quote: 'T3,Investigate confirmation email failure,,To do,' },
      { source: 'gh',    quote: '"number": 21 … "assignee": null' },
    ],
  },
  {
    id: 6,
    type: 'Risk',
    text: 'Confirmation emails may fail mainly for college email addresses.',
    status: 'inferred',
    evidence: [
      { source: 'n14', quote: 'Seems to happen with college email addresses.' },
    ],
  },
  {
    id: 7,
    type: 'Open question',
    text: 'PR #14 (event email reminders) was reverted and no reason is recorded.',
    status: 'missing',
    evidence: [
      { source: 'gh', quote: '"state": "reverted" … "Riya: Reverting this for now."' },
    ],
  },
  {
    id: 8,
    type: 'Next action',
    text: 'No one owns writing the deployment guide.',
    status: 'missing',
    evidence: [
      { source: 'tasks', quote: 'T5,Write deployment guide,,To do,' },
    ],
  },
  {
    id: 9,
    type: 'Contact',
    text: 'Mr. Sharma at the college IT office handles domain and hosting issues.',
    status: 'verified',
    evidence: [
      { source: 'n14', quote: 'Contact for domain and hosting issues: the college IT office (Mr. Sharma).' },
    ],
  },
  {
    id: 10,
    type: 'Contact',
    text: 'Dev renews the domain every August.',
    status: 'verified',
    evidence: [
      { source: 'n12', quote: 'Dev renews the domain every August.' },
    ],
  },
  {
    id: 11,
    type: 'Risk',
    text: 'Sponsor money is delayed and the club has not been told.',
    status: 'verified',
    evidence: [
      { source: 'chat', quote: 'Not yet. Let’s wait until the sponsor confirms the new date.' },
    ],
  },
  {
    id: 12,
    type: 'Risk',
    text: 'A deployment key (rzp_test_••••••••) was shared in chat. It should move to a password manager.',
    status: 'verified',
    evidence: [
      { source: 'chat', quote: 'the deployment key for the server is razorpay_deploy_key=rzp_test_••••••••' },
    ],
  },
].map(claim => ({ ...claim, review: 'pending' }));

// Questions for the departing person (gap interview)
const QUESTIONS = [
  {
    type: 'Open question',
    question: 'PR #14 (event email reminders) was reverted but no reason is recorded. What happened?',
  },
  {
    type: 'Decision',
    question: 'The Razorpay deadline appears as 30 September and 15 October. Which date is current?',
  },
  {
    type: 'Owner',
    question: 'Who should own the confirmation email bug (issue #21)?',
  },
];

// "Your first week" checklist for each role
const PLAN = {
  rev: [
    'Check every restricted claim before sharing.',
    'Resolve the Razorpay deadline conflict.',
    'Confirm who takes the three unowned items.',
  ],
  dev: [
    'Read the Razorpay decision and ask Karan which deadline holds.',
    'Contact Mr. Sharma at the college IT office about domain and hosting.',
    'Pick up the confirmation email bug, which has no owner.',
    'Ask Riya why PR #14 was reverted.',
  ],
  non: [
    'Read the Razorpay decision to understand why payments changed.',
    'Contact Mr. Sharma at the college IT office for domain and hosting questions.',
    'Ask the project lead who now owns the email problem.',
  ],
};

// How claim types are grouped on the Handover tab
const HANDOVER_GROUPS = [
  { title: 'Decisions',            types: ['Decision'] },
  { title: 'Ownership',            types: ['Owner'] },
  { title: 'Risks and open items', types: ['Risk', 'Blocker', 'Open question', 'Next action'] },
  { title: 'Contacts',             types: ['Contact'] },
];

// Extra explanation shown in the evidence panel for some statuses
const STATUS_NOTES = {
  conflicting: '<strong>Conflict:</strong> sources disagree. Confirm which one is current before approving.',
  missing:     '<strong>Missing:</strong> expected information is not in any source. The gap interview asks the leaver.',
};

const TAB_NAMES = ['Connect', 'Review', 'Gap interview', 'Handover'];


/* ==========================================================================
   2. STATE
   ========================================================================== */

let selectedId = null;      // claim currently open in the evidence panel
let nextClaimId = 100;      // ids for claims created by the gap interview
const versions = [];        // published versions: { number, items, time }
const acknowledgements = []; // { version, role, time }


/* ==========================================================================
   3. HELPERS
   ========================================================================== */

const $  = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);

const escapeHtml = value =>
  String(value).replace(/[&<>"]/g, char => ({
    '&': '&amp;',  
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
  }[char]));

const timeNow = () =>
  new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

const roleNames = roles => roles.map(role => ROLES[role]).join(', ');

// A claim is visible only if the role can open every source it cites
const canSee = (claim, role) =>
  claim.evidence.every(e => SOURCES[e.source].roles.includes(role));

let toastTimer;
function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('on'), 1800);
}


/* ==========================================================================
   4. NAVIGATION (tabs)
   ========================================================================== */

function buildTabs() {
  TAB_NAMES.forEach((name, index) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = name;
    button.setAttribute('role', 'tab');
    button.onclick = () => go(index);
    $('#tabs').append(button);
  });
}

// Tabs that need fresh content each time they are opened
const TAB_RENDERERS = {
  1: renderReview,
  2: renderQuestions,
  3: renderHandover,
};

function go(index) {
  $$('section').forEach((section, i) => section.classList.toggle('on', i === index));
  [...$('#tabs').children].forEach((tab, i) => tab.setAttribute('aria-selected', i === index));
  TAB_RENDERERS[index]?.();
  window.scrollTo(0, 0);
}


/* ==========================================================================
   5. TAB 1: CONNECT SOURCES
   ========================================================================== */

function renderSources() {
  const rows = Object.values(SOURCES).map(source => `
    <tr>
      <td>${source.name}</td>
      <td>${source.roles.map(role => `<span class="chip">${ROLES[role]}</span>`).join(' ')}</td>
    </tr>`);

  $('#srcTable').innerHTML =
    '<tr><th>Source</th><th>Who can open it</th></tr>' + rows.join('');
}


/* ==========================================================================
   6. TAB 2: REVIEW CLAIMS
   ========================================================================== */

function renderReview() {
  renderSummary();
  renderClaimList();
  renderPanel();
  renderVersions();
}

function renderSummary() {
  const countWithStatus = status => claims.filter(c => c.status === status).length;
  const approved = claims.filter(c => c.review === 'approved').length;

  const statusBadges = Object.keys(STATUS_LABELS)
    .filter(status => countWithStatus(status) > 0)
    .map(status =>
      `<span class="badge ${status}">${countWithStatus(status)} ${STATUS_LABELS[status].toLowerCase()}</span>`);

  $('#sum').innerHTML =
    statusBadges.join('') +
    `<span class="badge total">${approved} approved of ${claims.length}</span>`;
}

function renderClaimList() {
  $('#claimList').innerHTML = claims.map(claim => {
    const classes = [
      'claim',
      claim.status,
      claim.review === 'rejected' && 'rej',
      selectedId === claim.id && 'sel',
    ].filter(Boolean).join(' ');

    return `
      <div class="${classes}" tabindex="0" data-id="${claim.id}">
        <div class="txt">${escapeHtml(claim.text)}</div>
        <div class="meta">
          <span class="chip">${claim.type}</span>
          <span class="badge ${claim.status}">${STATUS_LABELS[claim.status]}</span>
          <span class="state-${claim.review}">${REVIEW_LABELS[claim.review]}</span>
        </div>
      </div>`;
  }).join('');
}

function renderPanel() {
  const panel = $('#panel');
  const claim = claims.find(c => c.id === selectedId);

  if (!claim) {
    panel.innerHTML = `
      <strong>Evidence</strong>
      <p class="muted">Select a claim to see the exact quote behind it and who can see it.</p>`;
    return;
  }

  const note = STATUS_NOTES[claim.status];

  panel.innerHTML = `
    <strong>Evidence</strong>
    <label class="note" for="ed">Claim text (edit if wrong)</label>
    <textarea id="ed" rows="3">${escapeHtml(claim.text)}</textarea>
    ${panelEvidenceHtml(claim)}
    ${note ? `<p class="note">${note}</p>` : ''}
    <div class="actions">
      <button type="button" class="b p" id="bA">Approve</button>
      <button type="button" class="b" id="bS">Save edit</button>
      <button type="button" class="b" id="bR">Reject</button>
    </div>`;

  // Approving and saving both keep whatever the reviewer typed in the box
  const saveEditedText = () => {
    claim.text = $('#ed').value.trim() || claim.text;
  };

  $('#bA').onclick = () => {
    saveEditedText();
    claim.review = 'approved';
    renderReview();
  };
  $('#bS').onclick = () => {
    saveEditedText();
    renderReview();
    toast('Edit saved');
  };
  $('#bR').onclick = () => {
    claim.review = 'rejected';
    renderReview();
  };
}

function panelEvidenceHtml(claim) {
  if (!claim.evidence.length) {
    return '<blockquote>Answer given by the departing person. Not yet checked against a source.</blockquote>';
  }
  return claim.evidence.map(e => `
    <blockquote>“${escapeHtml(e.quote)}”</blockquote>
    <div class="note">From ${SOURCES[e.source].name}. Visible to: ${roleNames(SOURCES[e.source].roles)}</div>`
  ).join('');
}

function renderVersions() {
  $('#verList').innerHTML = versions.length
    ? versions
        .map(v => `Version ${v.number}: ${v.items.length} approved claims, published ${v.time} by Reviewer`)
        .join('<br>')
    : 'No versions yet.';
}

function selectClaim(id) {
  selectedId = id;
  renderReview();
}

function approveAllVerified() {
  claims.forEach(claim => {
    if (claim.status === 'verified' && claim.review === 'pending') {
      claim.review = 'approved';
    }
  });
  renderReview();
  toast('Verified claims approved');
}

function publishVersion() {
  // Snapshot the approved claims so later edits don't change a published version
  const items = claims
    .filter(claim => claim.review === 'approved')
    .map(claim => ({ ...claim, evidence: claim.evidence.map(e => ({ ...e })) }));

  if (!items.length) {
    toast('Approve at least one claim first');
    return;
  }

  versions.push({ number: versions.length + 1, items, time: timeNow() });
  renderReview();
  toast(`Published version ${versions.length}`);
}


/* ==========================================================================
   7. TAB 3: GAP INTERVIEW
   ========================================================================== */

function renderQuestions() {
  $('#qs').innerHTML = QUESTIONS.map((q, i) => `
    <div class="card">
      <span class="chip">${q.type}</span>
      <p class="question"><strong>${escapeHtml(q.question)}</strong></p>
      <label class="note" for="a${i}">Riya’s answer</label>
      <textarea id="a${i}" rows="2"></textarea>
      <div class="answer-row">
        <button type="button" class="b p" data-q="${i}">Save answer</button>
        <span class="note" id="d${i}"></span>
      </div>
    </div>`).join('');

  $$('[data-q]').forEach(button => {
    button.onclick = () => saveAnswer(Number(button.dataset.q), button);
  });
}

// An answer becomes a new claim marked "stated", never "verified"
function saveAnswer(index, button) {
  const answer = $(`#a${index}`).value.trim();
  if (!answer) {
    toast('Write an answer first');
    return;
  }

  claims.push({
    id: nextClaimId++,
    type: QUESTIONS[index].type,
    text: `Stated by Riya: ${answer}`,
    status: 'stated',
    evidence: [],
    review: 'pending',
  });

  $(`#d${index}`).textContent = 'Saved as a claim awaiting review.';
  $(`#a${index}`).value = '';
  button.disabled = true;
}


/* ==========================================================================
   8. TAB 4: HANDOVER
   ========================================================================== */

function renderHandover() {
  const role = $('#role').value;
  const container = $('#hand');
  const version = versions[versions.length - 1];

  if (!version) {
    container.innerHTML = `
      <div class="card">
        <strong>No handover published yet.</strong>
        <p class="muted">Approve claims in the Review tab, then publish a version.</p>
        <button type="button" class="b p" data-go="1">Go to review</button>
      </div>`;
    container.querySelector('[data-go]').onclick = () => go(1);
    return;
  }

  container.innerHTML =
    planCardHtml(role, version) +
    HANDOVER_GROUPS.map(group => groupHtml(group, version, role)).join('') +
    `<div class="card ack-card">${acknowledgementHtml(role, version)}</div>`;

  const ackButton = $('#ack');
  if (ackButton) {
    ackButton.onclick = () => {
      acknowledgements.push({ version: version.number, role, time: timeNow() });
      renderHandover();
      toast('Receipt recorded');
    };
  }
}

function planCardHtml(role, version) {
  return `
    <div class="card">
      <h2>Your first week</h2>
      <p class="note">Handover version ${version.number} for ${ROLES[role]}.</p>
      <ol class="plan">${PLAN[role].map(step => `<li>${step}</li>`).join('')}</ol>
    </div>`;
}

function groupHtml(group, version, role) {
  const items = version.items.filter(claim => group.types.includes(claim.type));
  if (!items.length) return '';

  const cards = items.map(claim =>
    canSee(claim, role)
      ? handoverClaimHtml(claim)
      : '<div class="locked">Restricted item. Ask the reviewer.</div>');

  return `<h3>${group.title}</h3>${cards.join('')}`;
}

function handoverClaimHtml(claim) {
  const sourceChips = claim.evidence
    .map(e => `<span class="chip" title="${escapeHtml(e.quote)}">${SOURCES[e.source].name}</span>`)
    .join('');

  const evidenceToggle = claim.evidence.length
    ? `<details class="evidence">
         <summary class="note">Show evidence</summary>
         ${claim.evidence.map(e => `<blockquote>“${escapeHtml(e.quote)}”</blockquote>`).join('')}
       </details>`
    : '';

  return `
    <div class="claim ${claim.status} static">
      <div>${escapeHtml(claim.text)}</div>
      <div class="meta">
        <span class="badge ${claim.status}">${STATUS_LABELS[claim.status]}</span>
        ${sourceChips}
      </div>
      ${evidenceToggle}
    </div>`;
}

function acknowledgementHtml(role, version) {
  if (role === 'rev') {
    return '<span class="note">The reviewer view is for approving. Switch to an incoming role to acknowledge receipt.</span>';
  }

  const done = acknowledgements.find(a => a.version === version.number && a.role === role);
  if (done) {
    return `<strong>Acknowledged.</strong> <span class="note">${ROLES[role]} acknowledged version ${version.number} at ${done.time}.</span>`;
  }
  return '<button type="button" class="b p" id="ack">Acknowledge receipt</button>';
}


/* ==========================================================================
   9. STARTUP: attach event listeners and show the first tab
   ========================================================================== */

// Claim list: one listener handles clicks and Enter on any claim
function claimIdFromEvent(event) {
  const el = event.target.closest('.claim');
  return el ? Number(el.dataset.id) : null;
}

$('#claimList').addEventListener('click', event => {
  const id = claimIdFromEvent(event);
  if (id !== null) selectClaim(id);
});

$('#claimList').addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  const id = claimIdFromEvent(event);
  if (id !== null) selectClaim(id);
});

$('#apprVer').onclick = approveAllVerified;
$('#pubBtn').onclick = publishVersion;
$('#role').onchange = renderHandover;

$$('[data-go]').forEach(button => {
  button.onclick = () => go(Number(button.dataset.go));
});

buildTabs();
renderSources();
go(0);
