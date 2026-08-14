const runForm = document.querySelector('#run-form');
const runButton = document.querySelector('#run-button');
const message = document.querySelector('#run-message');
const timeline = document.querySelector('#timeline');
const eventCount = document.querySelector('#event-count');
const stateList = document.querySelector('#state-list');
const eventDetail = document.querySelector('#event-detail');
let sandboxAvailable = false;
let counters = {model: 0, command: 0, failed: 0};

fetch('/api/status').then(r => r.json()).then(status => {
  sandboxAvailable = status.sandbox_available;
  document.querySelector('#sandbox-status').innerHTML = `<span class="pill ${sandboxAvailable ? 'ok' : 'warn'}"><i class="dot"></i>${sandboxAvailable ? 'Docker 沙箱已就绪' : 'Docker 未就绪：仅可预览'}</span><span class="pill">命令网络：关闭</span><span class="pill">会话目录：一次性副本</span><span class="pill">事件内容：脱敏预览</span>`;
  runButton.disabled = !sandboxAvailable;
  renderWorkflow(status.harness_flow);
});

document.querySelector('#provider').addEventListener('change', event => {
  document.querySelector('#api-base').value = event.target.value === 'ollama-cloud' ? 'https://ollama.com/api' : 'https://api.openai.com/v1';
});

runForm.addEventListener('submit', async event => {
  event.preventDefault(); if (!sandboxAvailable) return;
  message.textContent = ''; runButton.disabled = true; timeline.innerHTML = '';
  counters = {model: 0, command: 0, failed: 0}; renderMetrics('启动中', null);
  try {
    const response = await fetch('/api/runs', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({provider:value('provider'), api_base:value('api-base'), model:value('model'), api_key:value('api-key'), task:value('task')})});
    const data = await response.json(); if (!response.ok) throw new Error(data.error); streamEvents(data.run_id);
  } catch (error) { message.textContent = error.message || '无法启动运行'; runButton.disabled = false; renderMetrics('启动失败', null); }
});

function streamEvents(runId) {
  const source = new EventSource(`/api/runs/${runId}/events`);
  source.onmessage = event => renderEvent(JSON.parse(event.data));
  source.onerror = async () => {
    source.close(); runButton.disabled = !sandboxAvailable;
    const snapshot = await fetch(`/api/runs/${runId}`).then(r => r.json());
    if (snapshot.error) message.textContent = snapshot.error;
    else if (snapshot.result) message.textContent = `运行结束：${snapshot.result.exit_status}`;
    renderMetrics(snapshot.error ? '失败' : snapshot.result?.exit_status || '已停止', snapshot.metrics);
  };
}

function renderEvent(event) {
  if (event.event === 'model_response') counters.model += 1;
  if (event.event === 'command_finished') { counters.command += 1; if (event.returncode !== 0) counters.failed += 1; }
  const phase = event.phase || inferPhase(event.event); activatePhase(phase);
  if (event.harness_flow) renderWorkflow(event.harness_flow);
  const card = document.createElement('article'); card.className = `event ${phase}`; card.tabIndex = 0;
  const badges = [event.duration_ms !== undefined ? `${event.duration_ms} ms` : '', event.returncode !== undefined ? `rc ${event.returncode}` : '', event.output_line_count !== undefined ? `${event.output_line_count} lines` : ''].filter(Boolean).map(item => `<em>${escapeHtml(item)}</em>`).join('');
  const preview = event.response_preview || event.output_preview || event.command || '';
  card.innerHTML = `<div class="event-top"><span>#${event.sequence} · step ${event.step} · ${escapeHtml(phase)}</span><span>${new Date(event.timestamp).toLocaleTimeString()}</span></div><strong>${escapeHtml(event.event)}</strong><span>${escapeHtml(event.summary)}</span><div class="event-badges">${badges}</div>${preview ? `<code>${escapeHtml(preview)}</code>` : ''}`;
  card.addEventListener('click', () => inspectEvent(event, card)); card.addEventListener('keydown', key => { if (key.key === 'Enter') inspectEvent(event, card); });
  timeline.append(card); timeline.scrollTop = timeline.scrollHeight; eventCount.textContent = `${event.sequence} 个事件`;
  stateList.innerHTML = `<div class="state"><small>运行</small><b>${event.event === 'run_finished' ? event.exit_status : '进行中'}</b></div><div class="state"><small>当前阶段</small><b>${phaseLabel(phase)}</b></div><div class="state"><small>步骤</small><b>${event.step}</b></div>`;
  renderMetrics(event.event === 'run_finished' ? event.exit_status : '进行中', null);
  inspectEvent(event, card);
}

function inspectEvent(event, card) {
  document.querySelectorAll('.event.selected').forEach(item => item.classList.remove('selected')); card.classList.add('selected');
  const hidden = new Set(['timestamp', 'sequence', 'event', 'phase', 'summary', 'harness_flow']);
  const rows = Object.entries(event).filter(([key]) => !hidden.has(key)).map(([key, val]) => `<div><small>${escapeHtml(key)}</small><pre>${escapeHtml(typeof val === 'object' ? JSON.stringify(val, null, 2) : val)}</pre></div>`).join('');
  eventDetail.innerHTML = `<h3>${escapeHtml(event.event)}</h3><p>${escapeHtml(event.summary)}</p>${rows || '<p class="hint">此事件没有额外公开字段。</p>'}`;
}

function renderMetrics(status, metrics) {
  const values = metrics || {model_calls:counters.model, command_count:counters.command, failed_command_count:counters.failed, duration_ms:null};
  document.querySelector('#metric-strip').innerHTML = `<div class="metric"><small>运行状态</small><b>${escapeHtml(status)}</b></div><div class="metric"><small>模型调用</small><b>${values.model_calls ?? counters.model}</b></div><div class="metric"><small>沙箱命令</small><b>${values.command_count ?? counters.command}</b></div><div class="metric"><small>失败命令</small><b>${values.failed_command_count ?? counters.failed}</b></div><div class="metric"><small>总耗时</small><b>${values.duration_ms == null ? '—' : `${values.duration_ms} ms`}</b></div>`;
}

function renderWorkflow(flow) {
  if (!flow) return;
  document.querySelector('#workflow-rail').innerHTML = flow.map(node => `<div class="workflow-node ${node.enabled ? '' : 'disabled'}"><span>${escapeHtml(node.label)}</span><small>${node.enabled ? 'enabled' : 'skipped'}</small></div>`).join('');
}
function activatePhase(phase) { document.querySelectorAll('#phase-rail [data-phase]').forEach(item => item.classList.toggle('active', item.dataset.phase === phase)); }
function inferPhase(name) { return name.includes('model') ? 'model' : name.includes('verification') ? 'verification' : name.includes('command') || name.includes('sandbox') ? 'sandbox' : 'agent'; }
function phaseLabel(phase) { return {agent:'Agent 控制', model:'模型交互', sandbox:'沙箱执行', verification:'结果验证'}[phase] || phase; }
function value(id) { return document.querySelector(`#${id}`).value.trim(); }
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value ?? ''); return div.innerHTML; }
