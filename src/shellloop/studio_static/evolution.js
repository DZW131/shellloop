const form = document.querySelector('#proposal-form');
const proposalButton = document.querySelector('#proposal-button');
const message = document.querySelector('#proposal-message');
const summary = document.querySelector('#proposal-summary');
const diff = document.querySelector('#diff');
const status = document.querySelector('#proposal-status');
const verifyButton = document.querySelector('#verify-button');
const applyButton = document.querySelector('#apply-button');
let proposal = null;

document.querySelector('#provider').addEventListener('change', event => { document.querySelector('#api-base').value = event.target.value === 'ollama-cloud' ? 'https://ollama.com/api' : 'https://api.openai.com/v1'; });

form.addEventListener('submit', async event => {
  event.preventDefault(); message.textContent = ''; proposalButton.disabled = true;
  try {
    const response = await fetch('/api/proposals', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({provider:value('provider'), api_base:value('api-base'), model:value('model'), api_key:value('api-key'), request:value('request')})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); proposal = data; renderProposal();
  } catch (error) { message.textContent = error.message || '无法生成候选方案'; } finally { proposalButton.disabled = false; }
});

verifyButton.addEventListener('click', async () => { await action('verify'); });
applyButton.addEventListener('click', async () => { if (confirm('测试已通过。确认将候选 Harness 配置写入正式项目吗？')) await action('apply'); });

async function action(name) {
  if (!proposal) return; message.textContent = ''; verifyButton.disabled = true; applyButton.disabled = true;
  try {
    const response = await fetch(`/api/proposals/${proposal.id}/${name}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); proposal = data; renderProposal();
  } catch (error) { message.textContent = error.message || '操作失败'; renderProposal(); }
}
function renderProposal() {
  summary.textContent = proposal.summary; status.textContent = proposal.applied ? '已由用户批准并应用' : proposal.verified ? '沙箱验证已通过' : '候选方案待验证';
  diff.innerHTML = Object.keys(proposal.current).map(key => `<div class="diff-row"><b>${key}</b><span class="old">${escapeHtml(preview(proposal.current[key]))}</span><span class="new">${escapeHtml(preview(proposal.candidate[key]))}</span></div>`).join('');
  verifyButton.disabled = proposal.verified || proposal.applied; applyButton.disabled = !proposal.verified || proposal.applied;
  document.querySelectorAll('#flow .flow-node').forEach((node,index) => { node.classList.toggle('good', index === 1 || (index === 2 && proposal.verified) || (index > 2 && proposal.applied)); node.classList.toggle('active', index === 2 && !proposal.verified); });
}
function value(id) { return document.querySelector(`#${id}`).value.trim(); }
function preview(value) { const text = String(value).replace(/\n/g, ' ↵ '); return text.length > 220 ? `${text.slice(0,217)}...` : text; }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value); return div.innerHTML; }
