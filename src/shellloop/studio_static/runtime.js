const runForm = document.querySelector('#run-form');
const runButton = document.querySelector('#run-button');
const message = document.querySelector('#run-message');
const timeline = document.querySelector('#timeline');
const eventCount = document.querySelector('#event-count');
const stateList = document.querySelector('#state-list');
let sandboxAvailable = false;

fetch('/api/status').then(r => r.json()).then(status => {
  sandboxAvailable = status.sandbox_available;
  document.querySelector('#sandbox-status').innerHTML = `<span class="pill ${sandboxAvailable ? 'ok' : 'warn'}"><i class="dot"></i>${sandboxAvailable ? 'Docker 沙箱已就绪' : 'Docker 未就绪：仅可预览'}</span><span class="pill">命令网络：关闭</span><span class="pill">会话目录：一次性副本</span>`;
  runButton.disabled = !sandboxAvailable;
});

document.querySelector('#provider').addEventListener('change', event => {
  document.querySelector('#api-base').value = event.target.value === 'ollama-cloud' ? 'https://ollama.com/api' : 'https://api.openai.com/v1';
});

runForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!sandboxAvailable) return;
  message.textContent = '';
  runButton.disabled = true;
  timeline.innerHTML = '';
  const payload = { provider: value('provider'), api_base: value('api-base'), model: value('model'), api_key: value('api-key'), task: value('task') };
  try {
    const response = await fetch('/api/runs', {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    streamEvents(data.run_id);
  } catch (error) { message.textContent = error.message || '无法启动运行'; runButton.disabled = false; }
});

function value(id) { return document.querySelector(`#${id}`).value.trim(); }
function streamEvents(runId) {
  const source = new EventSource(`/api/runs/${runId}/events`);
  source.onmessage = event => renderEvent(JSON.parse(event.data));
  source.onerror = async () => {
    source.close(); runButton.disabled = false;
    const snapshot = await fetch(`/api/runs/${runId}`).then(r => r.json());
    if (snapshot.error) message.textContent = snapshot.error;
    else if (snapshot.result) message.textContent = `运行结束：${snapshot.result.exit_status}`;
  };
}
function renderEvent(event) {
  const kind = event.event.includes('model') ? 'model' : event.event.includes('command') || event.event.includes('sandbox') ? 'sandbox' : event.event.includes('finished') ? 'done' : event.event.includes('failed') ? 'failed' : '';
  const card = document.createElement('article'); card.className = `event ${kind}`;
  const extra = event.command ? `<code>${escapeHtml(event.command)}</code>` : event.returncode !== undefined ? `<code>returncode=${event.returncode} · finished=${Boolean(event.finished)}</code>` : '';
  card.innerHTML = `<div class="event-top"><span>#${event.sequence} · step ${event.step}</span><span>${new Date(event.timestamp).toLocaleTimeString()}</span></div><strong>${escapeHtml(event.event)}</strong><span>${escapeHtml(event.summary)}</span>${extra}`;
  timeline.append(card); timeline.scrollTop = timeline.scrollHeight; eventCount.textContent = `${event.sequence} 个事件`;
  stateList.innerHTML = `<div class="state"><small>运行</small><b>${event.event === 'run_finished' ? event.exit_status : '进行中'}</b></div><div class="state"><small>步骤</small><b>${event.step}</b></div><div class="state"><small>最后事件</small><b>${escapeHtml(event.event)}</b></div>`;
}
function escapeHtml(value) { const div = document.createElement('div'); div.textContent = String(value); return div.innerHTML; }
