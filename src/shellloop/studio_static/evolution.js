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

document.querySelector('#provider').addEventListener('change', event => { document.querySelector('#api-base').value = event.target.value === 'ollama-cloud' ? 'https://ollama.com/api' : 'https://api.openai.com/v1'; });
form.addEventListener('submit', async event => {
  event.preventDefault(); message.textContent = ''; proposalButton.disabled = true;
  try {
    const response = await fetch('/api/proposals', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(credentials({request:value('request')}))});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); proposal = data; renderProposal();
  } catch (error) { message.textContent = error.message || '无法生成候选方案'; } finally { proposalButton.disabled = false; }
});
verifyButton.addEventListener('click', () => action('verify', {}));
compareButton.addEventListener('click', () => action('compare', credentials({evaluation_task:value('evaluation-task')})));
applyButton.addEventListener('click', async () => { if (confirm('静态测试已通过。确认将候选 Harness 写入正式项目吗？')) await action('apply', {}); });

async function action(name, body) {
  if (!proposal) return; message.textContent = ''; setActionsDisabled(true);
  try {
    const response = await fetch(`/api/proposals/${proposal.id}/${name}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); proposal = data; renderProposal();
  } catch (error) { message.textContent = error.message || '操作失败'; renderProposal(); }
}

function renderProposal() {
  summary.textContent = proposal.summary;
  status.textContent = proposal.applied ? '已批准并应用' : proposal.verified ? '测试通过，等待批准' : '候选方案待验证';
  diff.innerHTML = Object.keys(proposal.current).map(key => { const changed = proposal.changed_fields.includes(key); return `<div class="diff-row ${changed ? 'changed' : ''}"><b>${escapeHtml(key)}</b><span class="old">${escapeHtml(preview(proposal.current[key]))}</span><span class="new">${escapeHtml(preview(proposal.candidate[key]))}</span></div>`; }).join('');
  renderFlow('current-flow', proposal.current_flow); renderFlow('candidate-flow', proposal.candidate_flow);
  renderVerification(); renderComparison(); setActionsDisabled(false); updateApprovalFlow();
}

function renderFlow(id, flow) { document.querySelector(`#${id}`).innerHTML = flow.map(node => `<div class="workflow-node ${node.enabled ? '' : 'disabled'}"><span>${escapeHtml(node.label)}</span><small>${node.enabled ? 'enabled' : 'skipped'}</small></div>`).join(''); }
function renderVerification() {
  const evidence = document.querySelector('#verification-evidence'); const verification = proposal.verification;
  document.querySelector('#verification-status').textContent = verification.returncode === null ? '尚未验证' : proposal.verified ? '测试通过' : `测试失败 · rc ${verification.returncode}`;
  evidence.className = verification.returncode === null ? 'empty compact' : 'evidence-card';
  evidence.innerHTML = verification.returncode === null ? '在候选副本中运行完整 pytest，测试通过后才能批准。' : `<div><small>门禁命令</small><b>python -m pytest -q</b></div><div><small>返回码</small><b>${verification.returncode}</b></div><div><small>耗时</small><b>${verification.duration_ms} ms</b></div>`;
}
function renderComparison() {
  const target = document.querySelector('#comparison'); if (!proposal.comparison) { target.className = 'empty compact'; target.textContent = '对比成功状态、步数、失败命令、验证次数与耗时。'; return; }
  const base = proposal.comparison.baseline, candidate = proposal.comparison.candidate;
  const rows = [['成功', base.success, candidate.success], ['步骤', base.steps, candidate.steps], ['失败命令', base.failed_command_count, candidate.failed_command_count], ['验证次数', base.verification_count, candidate.verification_count], ['耗时 ms', base.duration_ms, candidate.duration_ms]];
  target.className = 'comparison-table'; target.innerHTML = `<div class="compare-head"><b>指标</b><b>当前</b><b>候选</b></div>${rows.map(row => `<div><span>${row[0]}</span><span>${row[1]}</span><span>${row[2]}</span></div>`).join('')}<p>${conclusionText(proposal.comparison.conclusion)} · ${escapeHtml(proposal.comparison.caution)}</p>`;
}
function setActionsDisabled(busy) { verifyButton.disabled = busy || proposal.verified || proposal.applied; compareButton.disabled = busy || proposal.applied; applyButton.disabled = busy || !proposal.verified || proposal.applied; }
function updateApprovalFlow() { document.querySelectorAll('#approval-flow .flow-node').forEach((node, index) => { const done = index <= 1 || (index === 2 && proposal.verified) || (index === 3 && proposal.comparison) || (index === 4 && proposal.applied); node.classList.toggle('good', Boolean(done)); node.classList.toggle('active', !done && ((index === 2 && !proposal.verified) || (index === 3 && proposal.verified && !proposal.comparison) || (index === 4 && proposal.verified))); }); }
function credentials(extra) { return {provider:value('provider'), api_base:value('api-base'), model:value('model'), api_key:value('api-key'), ...extra}; }
function conclusionText(value) { return {candidate_succeeded_where_baseline_failed:'候选版在本次运行中由失败转为成功', candidate_regressed:'候选版在本次运行中出现回退', candidate_used_fewer_failed_commands:'候选版使用了更少失败命令', candidate_used_fewer_steps:'候选版使用了更少步骤', inconclusive_single_run:'本次单次对比没有给出明确优势'}[value] || value; }
function value(id) { return document.querySelector(`#${id}`).value.trim(); }
function preview(value) { const text = String(value).replace(/\n/g, ' ↵ '); return text.length > 240 ? `${text.slice(0,237)}...` : text; }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value ?? ''); return div.innerHTML; }
