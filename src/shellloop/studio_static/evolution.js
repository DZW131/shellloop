const form = document.querySelector('#proposal-form');
const proposalButton = document.querySelector('#proposal-button');
const message = document.querySelector('#proposal-message');
const summary = document.querySelector('#proposal-summary');
const diff = document.querySelector('#diff');
const status = document.querySelector('#proposal-status');
const verifyButton = document.querySelector('#verify-button');
const compareButton = document.querySelector('#compare-button');
const applyButton = document.querySelector('#apply-button');
let proposal = null;
let comparisonRunning = false;

loadEvaluationCases();
loadVersions();
document.querySelector('#provider').addEventListener('change', event => {
  document.querySelector('#api-base').value = event.target.value === 'ollama-cloud' ? 'https://ollama.com/api' : 'https://api.openai.com/v1';
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  message.textContent = '';
  proposalButton.disabled = true;
  try {
    const response = await fetch('/api/proposals', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(credentials({request:value('request')}))});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    proposal = data;
    document.querySelector('#comparison-progress').innerHTML = '';
    renderProposal();
  } catch (error) {
    message.textContent = error.message || '无法生成候选方案';
  } finally {
    proposalButton.disabled = false;
  }
});

verifyButton.addEventListener('click', () => action('verify', {}));
compareButton.addEventListener('click', startComparison);
applyButton.addEventListener('click', async () => {
  if (confirm('静态测试已通过。确认将候选 Harness 写入正式项目吗？')) await action('apply', {});
});

async function action(name, body) {
  if (!proposal) return;
  message.textContent = '';
  setActionsDisabled(true);
  try {
    const response = await fetch(`/api/proposals/${proposal.id}/${name}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    proposal = data;
    renderProposal();
    if (name === 'apply') await loadVersions();
  } catch (error) {
    message.textContent = error.message || '操作失败';
    renderProposal();
  }
}

async function startComparison() {
  if (!proposal || comparisonRunning) return;
  message.textContent = '';
  comparisonRunning = true;
  setActionsDisabled(true);
  document.querySelector('#comparison-progress').innerHTML = '';
  document.querySelector('#comparison-status').textContent = '评测启动中';
  try {
    const evaluationCaseIds = [...document.querySelectorAll('[name="evaluation-case"]:checked')].map(input => input.value);
    const response = await fetch(`/api/proposals/${proposal.id}/compare`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(credentials({evaluation_case_ids:evaluationCaseIds, evaluation_task:value('evaluation-task')})),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    streamComparison(data.comparison_id);
  } catch (error) {
    comparisonRunning = false;
    message.textContent = error.message || '无法启动评测';
    document.querySelector('#comparison-status').textContent = '评测未启动';
    renderProposal();
  }
}

function streamComparison(comparisonId) {
  const source = new EventSource(`/api/comparisons/${comparisonId}/events`);
  source.onmessage = event => renderComparisonEvent(JSON.parse(event.data));
  source.onerror = async () => {
    source.close();
    await finishComparison(comparisonId);
  };
}

async function finishComparison(comparisonId) {
  let snapshot = await fetch(`/api/comparisons/${comparisonId}`).then(response => response.json());
  while (snapshot.running) {
    await new Promise(resolve => setTimeout(resolve, 800));
    snapshot = await fetch(`/api/comparisons/${comparisonId}`).then(response => response.json());
  }
  comparisonRunning = false;
  if (snapshot.error) {
    message.textContent = snapshot.error;
    document.querySelector('#comparison-status').textContent = '评测失败';
  } else {
    proposal.comparison = snapshot.comparison;
    document.querySelector('#comparison-status').textContent = `${snapshot.comparison.case_count} 个案例已完成`;
  }
  renderProposal();
}

function renderComparisonEvent(event) {
  const progress = document.querySelector('#comparison-progress');
  const item = document.createElement('div');
  item.className = `progress-event ${event.variant || 'suite'}`;
  const variant = event.variant ? (event.variant === 'baseline' ? '当前版' : '候选版') : '评测集';
  item.innerHTML = `<span>${escapeHtml(event.case_title || event.summary)}</span><b>${variant} · ${escapeHtml(event.event)}</b>${event.returncode === undefined ? '' : `<em>rc ${event.returncode}</em>`}`;
  progress.append(item);
  while (progress.children.length > 40) progress.firstElementChild.remove();
  progress.scrollTop = progress.scrollHeight;
  document.querySelector('#comparison-status').textContent = event.case_count ? `案例 ${event.case_index}/${event.case_count}` : `${variant}运行中`;
}

function renderProposal() {
  if (!proposal) return;
  summary.textContent = proposal.summary;
  const source = proposal.origin === 'restore' ? '恢复候选' : '改进候选';
  status.textContent = proposal.applied ? '已批准并应用' : proposal.verified ? `${source}测试通过，等待批准` : `${source}待验证`;
  diff.innerHTML = Object.keys(proposal.current).map(key => {
    const changed = proposal.changed_fields.includes(key);
    return `<div class="diff-row ${changed ? 'changed' : ''}"><b>${escapeHtml(key)}</b><span class="old">${escapeHtml(preview(proposal.current[key]))}</span><span class="new">${escapeHtml(preview(proposal.candidate[key]))}</span></div>`;
  }).join('');
  renderFlow('current-flow', proposal.current_flow);
  renderFlow('candidate-flow', proposal.candidate_flow);
  renderVerification();
  renderComparison();
  setActionsDisabled(false);
  updateApprovalFlow();
}

function renderFlow(id, flow) {
  document.querySelector(`#${id}`).innerHTML = flow.map(node => `<div class="workflow-node ${node.enabled ? '' : 'disabled'}"><span>${escapeHtml(node.label)}</span><small>${node.enabled ? 'enabled' : 'skipped'}</small></div>`).join('');
}

function renderVerification() {
  const evidence = document.querySelector('#verification-evidence');
  const verification = proposal.verification;
  document.querySelector('#verification-status').textContent = verification.returncode === null ? '尚未验证' : proposal.verified ? '测试通过' : `测试失败 · rc ${verification.returncode}`;
  evidence.className = verification.returncode === null ? 'empty compact' : 'evidence-card';
  evidence.innerHTML = verification.returncode === null ? '在候选副本中运行完整 pytest，测试通过后才能批准。' : `<div><small>门禁命令</small><b>python -m pytest -q</b></div><div><small>返回码</small><b>${verification.returncode}</b></div><div><small>耗时</small><b>${verification.duration_ms} ms</b></div>`;
}

function renderComparison() {
  const target = document.querySelector('#comparison');
  if (!proposal.comparison) {
    target.className = 'empty compact';
    target.textContent = '按案例对比真实成功、确定性检查、步数、失败命令与耗时。';
    return;
  }
  const base = proposal.comparison.baseline;
  const candidate = proposal.comparison.candidate;
  const rows = [
    ['完成声明', `${base.completed_count}/${proposal.comparison.case_count}`, `${candidate.completed_count}/${proposal.comparison.case_count}`],
    ['确定性成功', `${base.verified_success_count}/${base.checked_case_count}`, `${candidate.verified_success_count}/${candidate.checked_case_count}`],
    ['总步骤', base.steps, candidate.steps],
    ['失败命令', base.failed_command_count, candidate.failed_command_count],
    ['总耗时 ms', base.duration_ms, candidate.duration_ms],
  ];
  const cases = proposal.comparison.cases.map(item => `<article class="case-result"><b>${escapeHtml(item.title)}</b>${caseBadge('当前', item.baseline)}${caseBadge('候选', item.candidate)}</article>`).join('');
  target.className = 'comparison-table';
  target.innerHTML = `<div class="compare-head"><b>聚合指标</b><b>当前</b><b>候选</b></div>${rows.map(row => `<div><span>${row[0]}</span><span>${row[1]}</span><span>${row[2]}</span></div>`).join('')}<div class="case-results">${cases}</div><p>${conclusionText(proposal.comparison.conclusion)} · ${escapeHtml(proposal.comparison.caution)}</p>`;
}

async function loadEvaluationCases() {
  const target = document.querySelector('#evaluation-cases');
  try {
    const response = await fetch('/api/evaluation-cases');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    target.innerHTML = data.cases.map(item => `<label class="case-option"><input type="checkbox" name="evaluation-case" value="${escapeHtml(item.id)}" checked><span><b>${escapeHtml(item.title)}</b><small>${escapeHtml(item.description)}</small></span><em>${item.has_check ? '确定性检查' : '观察任务'}</em></label>`).join('');
  } catch (error) {
    target.innerHTML = `<p class="message">${escapeHtml(error.message || '无法读取评测集')}</p>`;
  }
}

async function loadVersions() {
  const target = document.querySelector('#version-list');
  try {
    const response = await fetch('/api/versions');
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    target.innerHTML = data.versions.map(version => `<article class="version-item ${version.active ? 'active' : ''}"><div><b>${version.active ? '当前版本' : sourceLabel(version.source)}</b><span>${escapeHtml(version.summary)}</span><small>${new Date(version.created_at).toLocaleString()} · ${escapeHtml(version.fingerprint)} · max_steps ${version.spec.max_steps}${version.restored_from ? ` · restored from ${escapeHtml(version.restored_from.slice(0,8))}` : ''}</small></div><button class="button secondary restore-button" data-version="${version.id}" ${version.active ? 'disabled' : ''}>生成恢复候选</button></article>`).join('');
    target.querySelectorAll('.restore-button:not(:disabled)').forEach(button => button.addEventListener('click', () => restoreVersion(button.dataset.version)));
  } catch (error) {
    target.innerHTML = `<p class="message">${escapeHtml(error.message || '无法读取版本历史')}</p>`;
  }
}

async function restoreVersion(versionId) {
  message.textContent = '';
  try {
    const response = await fetch(`/api/versions/${versionId}/restore`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    proposal = data;
    renderProposal();
    form.scrollIntoView({behavior:'smooth'});
  } catch (error) {
    message.textContent = error.message || '无法创建恢复候选';
  }
}

function setActionsDisabled(busy) {
  const locked = busy || comparisonRunning;
  verifyButton.disabled = locked || !proposal || proposal.verified || proposal.applied;
  compareButton.disabled = locked || !proposal || proposal.applied;
  applyButton.disabled = locked || !proposal || !proposal.verified || proposal.applied;
}

function updateApprovalFlow() {
  document.querySelectorAll('#approval-flow .flow-node').forEach((node, index) => {
    const done = index <= 1 || (index === 2 && proposal.verified) || (index === 3 && proposal.comparison) || (index === 4 && proposal.applied);
    node.classList.toggle('good', Boolean(done));
    node.classList.toggle('active', !done && ((index === 2 && !proposal.verified) || (index === 3 && proposal.verified && !proposal.comparison) || (index === 4 && proposal.verified)));
  });
}

function credentials(extra) { return {provider:value('provider'), api_base:value('api-base'), model:value('model'), api_key:value('api-key'), ...extra}; }
function caseBadge(label, metrics) { const checked = metrics.task_check_passed !== null; const passed = checked ? metrics.success : metrics.completed; return `<span class="${passed ? 'pass' : 'fail'}">${label} ${passed ? (checked ? '验证成功' : '已完成') : (checked ? '验证失败' : '未完成')}</span>`; }
function conclusionText(value) { return {candidate_improved_success_rate:'候选版在更多案例上得到真实成功', candidate_regressed_success_rate:'候选版的真实成功案例减少', candidate_used_fewer_failed_commands:'成功数相同，候选版使用了更少失败命令', candidate_used_fewer_steps:'成功数相同，候选版使用了更少步骤', inconclusive_suite:'本轮评测集没有给出明确优势'}[value] || value; }
function sourceLabel(value) { return {initial:'初始记录', external:'外部修改', 'natural-language':'自然语言演化', restore:'安全恢复', proposal:'候选应用', test:'测试版本'}[value] || value; }
function value(id) { return document.querySelector(`#${id}`).value.trim(); }
function preview(value) { const text = String(value).replace(/\n/g, ' ↵ '); return text.length > 240 ? `${text.slice(0,237)}...` : text; }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value ?? ''); return div.innerHTML; }
