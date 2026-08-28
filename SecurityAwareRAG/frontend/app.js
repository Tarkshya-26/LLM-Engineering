/* SecurityAwareRAG — agentic security architecture viewer.
 *
 * Renders demo.json. No security logic, no inference, no classification.
 *
 * Invariants carried over from the telemetry work:
 *   1. Layer status comes from `enforced_by_runs` / `constrained_by_runs`, aggregated
 *      over EVERY recorded run - never from the single stored trace. POISON-01 is why:
 *      its stored run shows the determination gate firing, but it fired on 3 of 8.
 *   2. Anything taken from one run says which run it was.
 *
 * Scenario titles below are display labels derived from `attack_type`. They never
 * influence what a layer is shown to have done - that comes only from the aggregates.
 */
'use strict';

let DATA = null;
const state = { caseId: 'TOOLMANIP-01', mode: 'governed', run: null };

const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const clip = (s, n) => { s = String(s || '').replace(/\s+/g, ' ').trim();
  return s.length > n ? s.slice(0, n) + '…' : s; };

/* Display labels only. Never consulted for security meaning. */
const SCENARIO = {
  clean_legitimate_query: 'Benign Request',
  cross_tenant_retrieval: 'Cross-Tenant Retrieval',
  poisoned_evidence: 'Data Poisoning',
  indirect_prompt_injection: 'Indirect Prompt Injection',
  tool_manipulation: 'Tool Manipulation',
  trusted_policy_vs_untrusted_claim: 'Trusted Policy vs Untrusted Claim',
  sensitive_data_leakage: 'Sensitive Data Leakage',
};

const theCase = () => DATA.cases.find(c => c.case_id === state.caseId);
const theSide = () => theCase()[state.mode === 'governed' ? 'on' : 'off'];
const runIdx = side => (state.run !== null && state.run < side.run_count)
  ? state.run : (side.detail_run_index ?? 0);
const theRun = side => (side.runs || [])[runIdx(side)] || null;
const layerName = id => (DATA.layers.find(l => l.id === id) || {}).name || id;

/* ---- aggregate layer status ------------------------------------------------ */
function layerStatus(c, side, id) {
  const runs = side.runs || [], n = runs.length || 1;
  let absent = 0, passed = 0, notReached = 0;
  runs.forEach(r => {
    const l = ((r.trace || {}).layers || []).find(x => x.id === id);
    if (!l) return;
    if (l.status === 'absent') absent++;
    else if (l.status === 'not_reached') notReached++;
    else if (l.status === 'passed') passed++;
  });
  const on = side === c.on;
  if (absent === runs.length && runs.length) return { s: 'absent', f: null };
  if (on && c.enforced_by_runs[id]) return { s: 'enforced', f: c.enforced_by_runs[id] };
  if (on && c.constrained_by_runs[id]) return { s: 'constrained', f: c.constrained_by_runs[id] };
  if (notReached) return { s: 'not_reached', f: `${notReached}/${n}` };
  return { s: 'passed', f: `${passed}/${n}` };
}

const trustDetail = run => (((run || {}).trace || {}).layers || [])
  .find(l => l.id === 'trust_aware_retrieval')?.detail || {};
const proposals = run => (((run || {}).trace || {}).actions || [])
  .filter(a => a.action !== 'escalate_to_human');

/* Rule strings, read from the recorded runs that carry them. */
function rulesFor(side, id) {
  const out = new Set();
  (side.runs || []).forEach(r => {
    const t = r.trace || {};
    if (id === 'determination_governance' && (t.determination || {}).decision === 'escalate')
      out.add(t.determination.rule);
    if (id === 'action_governance')
      (t.actions || []).forEach(a => { if (a.status === 'BLOCKED') out.add(a.rule); });
  });
  return [...out];
}

/* ---- flow ------------------------------------------------------------------ */

function node({ kind, k, n, s, chip, ghost, hot }) {
  return `<div class="node ${kind}${ghost ? ' ghost' : ''}${hot ? ' hot' : ''}">
    ${chip ? `<div class="chip">${esc(chip)}</div>` : ''}
    <div class="k">${esc(k)}</div><div class="n">${esc(n)}</div>
    ${s ? `<div class="s">${esc(s)}</div>` : ''}</div>`;
}
const ev = (lbl, html) => html
  ? `<div class="ev"><span class="lbl">${esc(lbl)}</span>${html}</div>` : '<div></div>';
const connector = dim => `<div class="row"><div class="conn${dim ? ' dim' : ''}"></div><div></div></div>`;

function renderFlow(c) {
  const side = theSide(), run = theRun(side), i = runIdx(side);
  const governed = state.mode === 'governed';
  const t = (run || {}).trace || {};
  const trust = trustDetail(run);
  const props = proposals(run);
  const dl = c.retrieval_delta;
  const rows = [];

  const push = (nodeHtml, evHtml, dim) => {
    if (rows.length) rows.push(connector(dim));
    rows.push(`<div class="row">${nodeHtml}${evHtml}</div>`);
  };

  // 1 user
  push(node({ kind: 'io', k: 'input', n: 'User request' }),
    ev('query', `<div style="color:var(--txt)">${esc(clip(c.query, 130))}</div>
      <div class="frac" style="margin-top:5px">requesting merchant · ${esc(c.requesting_merchant)}</div>`));

  // 2 retrieval
  const rst = layerStatus(c, side, 'retrieval');
  push(node({ kind: 'retrieval', k: 'step 1', n: 'RAG retrieval', s: 'Similarity search over the knowledge base', chip: rst.s }),
    ev('documents returned', `<div class="big">${(run || {}).retrieved?.length ?? 0}</div>
      <div style="margin-top:6px">${((run || {}).retrieved || []).map(d =>
        `<span class="pill ${d.trust_tier === 'trusted' ? 'trusted' : 'untrusted'}">${esc(d.document_id)}</span>`).join('')}</div>
      <div class="frac" style="margin-top:5px">recorded run ${i + 1} of ${side.run_count}</div>`));

  // 3-5 security boundaries
  const secs = [
    ['tenant_authorization', 'Tenant authorization', 'Restrict candidates to the authenticated merchant',
      () => (dl.off_other_tenant_documents.length || dl.on_other_tenant_documents.length)
        ? ev('other-merchant documents', `
            <div>baseline &nbsp;${dl.off_other_tenant_documents.map(x =>
              `<span class="pill untrusted">${esc(x)}</span>`).join('') || '<span class="pill none">none</span>'}</div>
            <div style="margin-top:5px">governed ${dl.on_other_tenant_documents.map(x =>
              `<span class="pill untrusted">${esc(x)}</span>`).join('') || '<span class="pill none">none recorded</span>'}</div>
            <div class="frac" style="margin-top:6px">retrieval evidence — not an enforcement claim</div>`)
        : ev('scope', `<span class="mono">${esc(JSON.stringify(
            (((run || {}).trace || {}).layers || []).find(l => l.id === 'tenant_authorization')?.detail?.authorized_scope || []))}</span>`)],
    ['trust_aware_retrieval', 'Trust & redaction', 'Separate authoritative policy from self-attested material; strip secrets',
      () => (trust.redactions || []).length
        ? ev('secrets removed before the model', `
            <div>${trust.documents_containing_secrets.map(x => `<span class="pill untrusted">${esc(x)}</span>`).join('')}</div>
            <div class="mono" style="margin-top:5px">${esc((trust.redactions || []).map(r => r.kinds.join(', ')).join(' · '))}</div>
            <div style="margin-top:6px">reaching model context
              <span class="big good">${esc(trust.secrets_reaching_model_context)}</span></div>`)
        : ev('evidence mix', `<span class="mono">${(trust.authoritative_documents || []).length} authoritative ·
            ${(trust.self_attested_documents || []).length} self-attested</span>`)],
    ['context_isolation', 'Context isolation', 'Retrieved data never enters the operator instruction channel',
      () => ev('channel', `<span class="mono">evidence delivered in the user channel</span>`)],
  ];
  secs.forEach(([id, name, sub, evf]) => {
    const st = layerStatus(c, side, id);
    const ghost = st.s === 'absent';
    push(node({ kind: 'sec', k: 'security boundary', n: name, s: sub,
        chip: ghost ? 'not present' : `${st.s} ${st.f || ''}`, ghost }),
      ghost ? ev('baseline', '<span class="frac">this boundary does not exist in the baseline pipeline</span>') : evf());
  });

  // 6 agent
  push(node({ kind: 'agent', k: 'reasoning component', n: 'AI agent',
      s: 'Reads evidence and reasons. Enforces nothing.' }),
    props.length
      ? ev('proposed action', `<div class="mono hot">⚠ ${esc(props[0].action)}(merchant_id='${esc(props[0].proposed_merchant_id)}')</div>
          <div style="margin-top:6px;color:var(--dim)">${esc(clip(props[0].justification, 150))}</div>
          <div class="frac" style="margin-top:6px">recorded run ${i + 1} of ${side.run_count}</div>`)
      : ev('response', `<div style="color:var(--dim)">${esc(clip((run || {}).answer, 150))}</div>
          <div class="frac" style="margin-top:5px">recorded run ${i + 1} of ${side.run_count}</div>`));

  // 7-8 governance
  [['determination_governance', 'Determination governance', 'Refuses a consequential determination unsupported by authoritative evidence'],
   ['action_governance', 'Action governance', 'Authorizes or blocks a proposed tool invocation, outside the model']]
  .forEach(([id, name, sub]) => {
    const st = layerStatus(c, side, id);
    const ghost = st.s === 'absent', hot = st.s === 'enforced';
    const rules = rulesFor(side, id);
    push(node({ kind: 'gov', k: 'deterministic governance', n: name, s: sub,
        chip: ghost ? 'not present' : `${st.s} ${st.f || ''}`, ghost, hot }),
      ghost ? ev('baseline', '<span class="frac">no governance layer in the baseline pipeline</span>')
        : hot ? ev('outcome', `<div class="mono hot">🛑 ${esc(rules.join(', '))}</div>
            <div class="frac" style="margin-top:6px">enforced on ${esc(st.f)} recorded runs</div>`)
          : ev('outcome', `<span class="frac">no blocking decision on any recorded run</span>`));
  });

  // 9 result
  const executed = t.executed === true;
  push(node({ kind: 'out', k: 'result', n: executed ? 'Action executed' : 'No action executed',
      chip: `executed: ${executed}` }),
    ev('recorded outcome', `<div class="big ${side.status === 'ATTACK_BLOCKED' || side.status === 'OK' ? 'good' : 'hot'}">
        ${esc(side.status.replace(/_/g, ' '))}</div>
      <div class="frac" style="margin-top:4px">${esc(side.stability || '')}</div>
      ${!governed ? '<div class="frac" style="margin-top:6px">the baseline pipeline exposes no tools — nothing could execute</div>' : ''}`));

  return `<div class="flow">${rows.join('')}</div>`;
}

/* ---- disclosures ----------------------------------------------------------- */
const kvr = (k, v) => `<div class="kvr"><div class="k">${esc(k)}</div><div class="v">${v}</div></div>`;

function renderDetails(c) {
  const side = theSide(), run = theRun(side), i = runIdx(side);
  const t = (run || {}).trace || {}, d = t.determination;
  return `<details><summary>Recorded run details
      <span class="cnt">${side.run_count} runs · ${esc(side.pipeline)}</span></summary>
    <div class="dbody">
      <div class="runbar"><span class="lab">run</span>
        ${(side.runs || []).map((r, k) => `<button data-run="${k}"
          class="${k === i ? 'on' : ''}">${k + 1}</button>`).join('')}
        <span class="lab" style="margin-left:10px">showing run ${i + 1} of ${side.run_count} — one run, not the whole case</span></div>
      ${d ? kvr('determination', `${esc(String(d.decision).toUpperCase())} — ${esc(d.rule)}`) + kvr('reason', esc(d.reason)) : ''}
      ${(t.actions || []).map(a => kvr(a.status.toLowerCase(),
        `${esc(a.action)}(merchant_id='${esc(a.proposed_merchant_id)}') — ${esc(a.rule)}`)).join('')}
      ${kvr('executed', esc(String(t.executed)))}
      ${(t.audit || []).length ? `<div style="margin-top:14px">${t.audit.map(l =>
        `<div class="aline ${(l.match(/\[(\w+)/) || [, ''])[1]}">${esc(l)}</div>`).join('')}</div>` : ''}
      <div style="margin-top:14px"><div class="eyebrow" style="margin-bottom:7px">Response</div>
        <pre>${esc((run || {}).answer || '')}</pre></div>
    </div></details>
    ${c.attack_documents.length ? `<details><summary>Retrieved case documents
      <span class="cnt">benchmark metadata · ${c.attack_documents.length}</span></summary>
      <div class="dbody">${c.attack_documents.map(id => {
        const doc = DATA.corpus[id]; if (!doc) return '';
        return `<div style="margin-top:13px">
          <div style="margin-bottom:8px">
            <span class="pill">${esc(id)}</span>
            <span class="pill ${doc.trust_tier === 'trusted' ? 'trusted' : 'untrusted'}">${esc(doc.trust_tier)}</span>
            <span class="pill">${esc(doc.merchant_id || 'first-party')}</span>
            <span class="pill">${esc(doc.classification)}</span></div>
          <pre>${esc(doc.content)}</pre></div>`; }).join('')}</div></details>` : ''}`;
}

const LIMITS = [
  ['Recorded runs are observations.', '8/8 means no failure was seen across those runs — not proof of determinism. 0/8 is not proof of safety.'],
  ['Constrained is not blocked.', 'Constrained boundaries restricted or transformed data without terminating the request. Only enforced layers produced a blocking decision.'],
  ['Retrieval deltas are retrieval evidence.', 'Candidates excluded by tenant scoping are never observable, so a difference in retrieved documents is not itself an enforcement claim.'],
  ['The baseline had no tools.', 'executed: false on the baseline means no tool existed to call, not that a call was prevented.'],
  ['The agent was not defended.', 'Where it proposed a consequential action it was persuaded by the injected evidence. Governance evaluated the proposal outside the model and refused it.'],
  ['This page enforces nothing.', 'It renders recorded evaluation runs and makes no network calls. Every value traces to a report in evaluation/reports/.'],
];

function render() {
  const c = theCase(), governed = state.mode === 'governed';
  document.getElementById('main').innerHTML = `
    <div class="head">
      <div class="eyebrow">${esc(c.case_id)}</div>
      <h1>${esc(SCENARIO[c.attack_type] || c.attack_type)}</h1>
      <div class="q">${esc(c.query)}</div>
    </div>
    <div class="switch">
      <button data-mode="baseline" class="${!governed ? 'on base' : ''}">BASELINE</button>
      <button data-mode="governed" class="${governed ? 'on' : ''}">GOVERNED</button>
    </div>
    <div class="switch-note">Same request, same recorded evidence. The toggle switches which
      recorded pipeline is shown — nothing executes.</div>
    <div class="legend">
      <span><i style="background:var(--sec)"></i>security boundary</span>
      <span><i style="background:var(--agent)"></i>reasoning</span>
      <span><i style="background:var(--gov)"></i>deterministic governance</span>
      <span><i style="background:var(--ok)"></i>result</span>
    </div>
    ${renderFlow(c)}
    <div class="outcome">
      <div><div class="eyebrow">Baseline outcome</div>
        <div class="v ${c.off.status === 'OK' ? 'neu' : 'bad'}">${esc(c.off.status.replace(/_/g, ' '))}</div>
        <div class="sub">${esc(c.off.stability || '')}</div></div>
      <div><div class="eyebrow">Governed outcome</div>
        <div class="v ${c.on.status === 'ATTACK_BLOCKED' || c.on.status === 'OK' ? 'good' : 'bad'}">
          ${esc(c.on.status.replace(/_/g, ' '))}</div>
        <div class="sub">${esc(c.on.stability || '')}</div></div>
    </div>
    ${renderDetails(c)}
    <div class="limits"><div class="eyebrow">What this shows — and what it does not</div>
      <ul>${LIMITS.map(([h, b]) => `<li><b>${esc(h)}</b> ${esc(b)}</li>`).join('')}</ul>
      <div class="note">${esc(DATA.source_reports.off.file)} · ${esc(DATA.source_reports.on.file)}</div>
    </div>`;
  renderNav();
}

function renderNav() {
  document.getElementById('nav').innerHTML = '<div class="eyebrow">Attack lab</div>' +
    DATA.cases.map(c => `<button data-case="${c.case_id}" class="${c.case_id === state.caseId ? 'on' : ''}">
      <span class="t">${esc(SCENARIO[c.attack_type] || c.attack_type)}</span>
      <span class="c">${esc(c.case_id)}</span></button>`).join('');
}

function renderStat() {
  const s = DATA.summary;
  document.getElementById('stat').innerHTML =
    `<span>attack success <b>${s.off.attacks_succeeded}/${s.off.attack_cases}</b> → <b>${s.on.attacks_succeeded}/${s.on.attack_cases}</b></span>
     <span>false positives <b>${s.off.false_positives}/${s.off.benign_cases}</b> → <b>${s.on.false_positives}/${s.on.benign_cases}</b></span>
     <span>latency <b>${s.off.mean_latency_s}s</b> → <b>${s.on.mean_latency_s}s</b></span>`;
}

document.addEventListener('click', e => {
  const b = e.target.closest('button'); if (!b) return;
  if (b.dataset.case) { state.caseId = b.dataset.case; state.run = null; render(); }
  else if (b.dataset.mode) { state.mode = b.dataset.mode; state.run = null; render(); }
  else if (b.dataset.run) {
    state.run = +b.dataset.run;
    const open = [...document.querySelectorAll('details')].map(d => d.open);
    render();
    document.querySelectorAll('details').forEach((d, i) => d.open = open[i]);
  }
});

fetch('./data/demo.json').then(r => r.json()).then(d => { DATA = d; renderStat(); render(); })
  .catch(e => { document.getElementById('main').innerHTML =
    `<p class="note">could not load ./data/demo.json — serve this directory over HTTP (${esc(e.message)})</p>`; });
