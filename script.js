const ROLES={rev:'Reviewer',dev:'Incoming developer',non:'Incoming non-technical member'};
const SRC={
 n12:{name:'meeting_notes_12.md',roles:['rev','dev','non']},
 n14:{name:'meeting_notes_14.md',roles:['rev','dev','non']},
 tasks:{name:'tasks.csv',roles:['rev','dev','non']},
 gh:{name:'github_export.json',roles:['rev','dev']},
 chat:{name:'leadership_chat_private.txt',roles:['rev']}};
let claims=[
 {id:1,type:'Decision',text:'The team switched from Stripe to Razorpay because Stripe did not support INR.',status:'verified',ev:[{s:'n12',q:'Stripe does not support INR payouts for our club account.'}]},
 {id:2,type:'Decision',text:'The Razorpay switch deadline is unclear: 30 September in one source, 15 October in two others.',status:'conflicting',ev:[{s:'n12',q:'Deadline for the switch: 30 September.'},{s:'n14',q:'Revised target for the Razorpay switch: 15 October, because of exams.'},{s:'tasks',q:'T1,Switch checkout to Razorpay,Karan,In progress,2026-10-15'}]},
 {id:3,type:'Owner',text:'Karan owns the Razorpay checkout work.',status:'verified',ev:[{s:'tasks',q:'T1,Switch checkout to Razorpay,Karan,In progress'}]},
 {id:4,type:'Owner',text:'Meera owns the mobile menu overlap fix.',status:'verified',ev:[{s:'tasks',q:'T2,Fix mobile menu overlap,Meera,To do'}]},
 {id:5,type:'Blocker',text:'No one owns the confirmation email failure (issue #21).',status:'missing',ev:[{s:'tasks',q:'T3,Investigate confirmation email failure,,To do,'},{s:'gh',q:'"number": 21 … "assignee": null'}]},
 {id:6,type:'Risk',text:'Confirmation emails may fail mainly for college email addresses.',status:'inferred',ev:[{s:'n14',q:'Seems to happen with college email addresses.'}]},
 {id:7,type:'Open question',text:'PR #14 (event email reminders) was reverted and no reason is recorded.',status:'missing',ev:[{s:'gh',q:'"state": "reverted" … "Riya: Reverting this for now."'}]},
 {id:8,type:'Next action',text:'No one owns writing the deployment guide.',status:'missing',ev:[{s:'tasks',q:'T5,Write deployment guide,,To do,'}]},
 {id:9,type:'Contact',text:'Mr. Sharma at the college IT office handles domain and hosting issues.',status:'verified',ev:[{s:'n14',q:'Contact for domain and hosting issues: the college IT office (Mr. Sharma).'}]},
 {id:10,type:'Contact',text:'Dev renews the domain every August.',status:'verified',ev:[{s:'n12',q:'Dev renews the domain every August.'}]},
 {id:11,type:'Risk',text:'Sponsor money is delayed and the club has not been told.',status:'verified',ev:[{s:'chat',q:'Not yet. Let’s wait until the sponsor confirms the new date.'}]},
 {id:12,type:'Risk',text:'A deployment key (rzp_test_••••••••) was shared in chat. It should move to a password manager.',status:'verified',ev:[{s:'chat',q:'the deployment key for the server is razorpay_deploy_key=rzp_test_••••••••'}]}
].map(c=>({...c,review:'pending'}));
const QS=[
 {t:'Open question',q:'PR #14 (event email reminders) was reverted but no reason is recorded. What happened?'},
 {t:'Decision',q:'The Razorpay deadline appears as 30 September and 15 October. Which date is current?'},
 {t:'Owner',q:'Who should own the confirmation email bug (issue #21)?'}];
let sel=null,versions=[],acks=[],nextId=100;
const $=s=>document.querySelector(s);
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const label={verified:'Verified',inferred:'Inferred',conflicting:'Conflicting',missing:'Missing',stated:'Stated by leaver'};
const canSee=(c,r)=>c.ev.every(e=>SRC[e.s].roles.includes(r));
function toast(m){const t=$('#toast');t.textContent=m;t.classList.add('on');clearTimeout(toast.h);toast.h=setTimeout(()=>t.classList.remove('on'),1800)}

const TABS=['Connect','Review','Gap interview','Handover'];
TABS.forEach((n,i)=>{const b=document.createElement('button');b.textContent=n;b.setAttribute('role','tab');b.onclick=()=>go(i);$('#tabs').append(b)});
function go(i){document.querySelectorAll('section').forEach((s,j)=>s.classList.toggle('on',i===j));
 [...$('#tabs').children].forEach((b,j)=>b.setAttribute('aria-selected',i===j));
 if(i===1)renderReview();if(i===2)renderQs();if(i===3)renderHand();window.scrollTo(0,0)}
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>go(+b.dataset.go));

$('#srcTable').innerHTML='<tr><th>Source</th><th>Who can open it</th></tr>'+Object.values(SRC).map(s=>`<tr><td>${s.name}</td><td>${s.roles.map(r=>`<span class="chip">${ROLES[r]}</span>`).join(' ')}</td></tr>`).join('');

function renderReview(){
 const n=k=>claims.filter(c=>c.status===k).length;
 $('#sum').innerHTML=Object.keys(label).filter(k=>n(k)).map(k=>`<span class="badge ${k}">${n(k)} ${label[k].toLowerCase()}</span>`).join('')+`<span class="badge" style="background:var(--bd)">${claims.filter(c=>c.review==='approved').length} approved of ${claims.length}</span>`;
 $('#claimList').innerHTML=claims.map(c=>`<div class="claim ${c.status} ${c.review==='rejected'?'rej':''} ${sel===c.id?'sel':''}" tabindex="0" data-id="${c.id}">
  <div class="txt">${esc(c.text)}</div>
  <div class="meta"><span class="chip">${c.type}</span><span class="badge ${c.status}">${label[c.status]}</span>
  <span class="state-${c.review}">${c.review==='pending'?'Needs review':c.review==='approved'?'Approved':'Rejected'}</span></div></div>`).join('');
 document.querySelectorAll('.claim').forEach(e=>{e.onclick=()=>{sel=+e.dataset.id;renderReview()};e.onkeydown=ev=>{if(ev.key==='Enter'){sel=+e.dataset.id;renderReview()}}});
 renderPanel();
 $('#verList').innerHTML=versions.length?versions.map(v=>`Version ${v.n}: ${v.items.length} approved claims, published ${v.time} by Reviewer`).join('<br>'):'No versions yet.';
}
function renderPanel(){
 const c=claims.find(x=>x.id===sel),p=$('#panel');
 if(!c){p.innerHTML='<b>Evidence</b><p class="muted">Select a claim to see the exact quote behind it and who can see it.</p>';return}
 p.innerHTML=`<b>Evidence</b>
 <label class="note" for="ed">Claim text (edit if wrong)</label>
 <textarea id="ed" rows="3">${esc(c.text)}</textarea>
 ${c.ev.length?c.ev.map(e=>`<blockquote>“${esc(e.q)}”</blockquote><div class="note">From ${SRC[e.s].name}. Visible to: ${SRC[e.s].roles.map(r=>ROLES[r]).join(', ')}</div>`).join(''):'<blockquote>Answer given by the departing person. Not yet checked against a source.</blockquote>'}
 ${c.status==='conflicting'?'<p class="note"><b>Conflict:</b> sources disagree. Confirm which one is current before approving.</p>':''}
 ${c.status==='missing'?'<p class="note"><b>Missing:</b> expected information is not in any source. The gap interview asks the leaver.</p>':''}
 <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
 <button class="b p" id="bA">Approve</button><button class="b" id="bS">Save edit</button><button class="b" id="bR">Reject</button></div>`;
 $('#bA').onclick=()=>{c.text=$('#ed').value.trim()||c.text;c.review='approved';renderReview()};
 $('#bS').onclick=()=>{c.text=$('#ed').value.trim()||c.text;renderReview();toast('Edit saved')};
 $('#bR').onclick=()=>{c.review='rejected';renderReview()};
}
$('#apprVer').onclick=()=>{claims.forEach(c=>{if(c.status==='verified'&&c.review==='pending')c.review='approved'});renderReview();toast('Verified claims approved')};
$('#pubBtn').onclick=()=>{const items=claims.filter(c=>c.review==='approved').map(c=>({...c,ev:c.ev.map(e=>({...e}))}));
 if(!items.length){toast('Approve at least one claim first');return}
 versions.push({n:versions.length+1,items,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});renderReview();toast('Published version '+versions.length)};

function renderQs(){
 $('#qs').innerHTML=QS.map((q,i)=>`<div class="card"><span class="chip">${q.t}</span><p style="margin:8px 0"><b>${esc(q.q)}</b></p>
 <label class="note" for="a${i}">Riya’s answer</label><textarea id="a${i}" rows="2"></textarea>
 <div style="margin-top:8px"><button class="b p" data-q="${i}">Save answer</button> <span class="note" id="d${i}"></span></div></div>`).join('');
 document.querySelectorAll('[data-q]').forEach(b=>b.onclick=()=>{const i=+b.dataset.q,v=$('#a'+i).value.trim();
  if(!v){toast('Write an answer first');return}
  claims.push({id:nextId++,type:QS[i].t,text:'Stated by Riya: '+v,status:'stated',ev:[],review:'pending'});
  $('#d'+i).textContent='Saved as a claim awaiting review.';$('#a'+i).value='';b.disabled=true});
}

const PLAN={
 rev:['Check every restricted claim before sharing.','Resolve the Razorpay deadline conflict.','Confirm who takes the three unowned items.'],
 dev:['Read the Razorpay decision and ask Karan which deadline holds.','Contact Mr. Sharma at the college IT office about domain and hosting.','Pick up the confirmation email bug, which has no owner.','Ask Riya why PR #14 was reverted.'],
 non:['Read the Razorpay decision to understand why payments changed.','Contact Mr. Sharma at the college IT office for domain and hosting questions.','Ask the project lead who now owns the email problem.']};
const GROUPS=[['Decisions',['Decision']],['Ownership',['Owner']],['Risks and open items',['Risk','Blocker','Open question','Next action']],['Contacts',['Contact']]];
function renderHand(){
 const r=$('#role').value,h=$('#hand'),v=versions[versions.length-1];
 if(!v){h.innerHTML='<div class="card"><b>No handover published yet.</b><p class="muted">Approve claims in the Review tab, then publish a version.</p><button class="b p" data-go="1">Go to review</button></div>';h.querySelector('[data-go]').onclick=()=>go(1);return}
 const mask=c=>c.ev.length?'':'';
 let out=`<div class="card"><h2>Your first week</h2><p class="note">Handover version ${v.n} for ${ROLES[r]}.</p><ol class="plan">${PLAN[r].map(x=>`<li>${x}</li>`).join('')}</ol></div>`;
 GROUPS.forEach(([title,types])=>{const items=v.items.filter(c=>types.includes(c.type));if(!items.length)return;
  out+=`<h3>${title}</h3>`+items.map(c=>canSee(c,r)?
   `<div class="claim ${c.status}" style="cursor:default"><div>${esc(c.text)}</div><div class="meta"><span class="badge ${c.status}">${label[c.status]}</span>${c.ev.map(e=>`<span class="chip" title="${esc(e.q)}">${SRC[e.s].name}</span>`).join('')}</div>${c.ev.length?`<details style="margin-top:6px"><summary class="note">Show evidence</summary>${c.ev.map(e=>`<blockquote>“${esc(e.q)}”</blockquote>`).join('')}</details>`:''}</div>`
   :`<div class="locked">Restricted item. Ask the reviewer.</div>`).join('')});
 const done=acks.filter(a=>a.n===v.n&&a.r===r);
 out+=`<div class="card" style="margin-top:16px">${r==='rev'?'<span class="note">The reviewer view is for approving. Switch to an incoming role to acknowledge receipt.</span>':done.length?`<b>Acknowledged.</b> <span class="note">${ROLES[r]} acknowledged version ${v.n} at ${done[0].time}.</span>`:'<button class="b p" id="ack">Acknowledge receipt</button>'}</div>`;
 h.innerHTML=out;
 const a=$('#ack');if(a)a.onclick=()=>{acks.push({n:v.n,r,time:new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})});renderHand();toast('Receipt recorded')};
}
$('#role').onchange=renderHand;
go(0);
