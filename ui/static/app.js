// Cascade — frontend logic.
// Single-page app: load presets/models, run jobs, stream SSE progress, view files.

const $ = (id) => document.getElementById(id);

const STEP_NAMES = ['use_cases', 'nfr', 'fr', 'code', 'tests', 'readme'];

const els = {
  preset: $('preset-select'),
  bt: $('bt'),
  bp: $('bp'),
  features: $('features'),
  skipUC: $('opt-skip-uc'),
  skipTests: $('opt-skip-tests'),
  selfCheck: $('opt-self-check'),
  generate: $('generate-btn'),
  download: $('download-btn'),
  steps: document.querySelectorAll('#steps li'),
  meta: $('meta'),
  fileTree: $('file-tree'),
  fileContent: $('file-content'),
  health: $('health'),
  costHint: $('cost-hint'),

  // settings modal
  settingsBtn: $('settings-btn'),
  settingsModal: $('settings-modal'),
  settingsClose: $('settings-close'),
  settingsSave: $('settings-save'),
  modelFastSel: $('model-fast'),
  modelSmartSel: $('model-smart'),
  modelFastMeta: $('model-fast-meta'),
  modelSmartMeta: $('model-smart-meta'),
  modelReset: $('model-reset'),

  // refinement
  refinePanel: $('refine-panel'),
  refineComment: $('refine-comment'),
  refineApply: $('refine-apply'),

  // wave 3
  previewBtn: $('preview-btn'),
  traceBtn: $('trace-btn'),
  historyBtn: $('history-btn'),
  previewModal: $('preview-modal'),
  previewFrame: $('preview-frame'),
  previewClose: $('preview-close'),
  previewReload: $('preview-reload'),
  previewOpen: $('preview-open'),
  traceModal: $('trace-modal'),
  traceClose: $('trace-close'),
  traceBody: $('trace-body'),
  historyPanel: $('history-panel'),
  historyClose: $('history-close'),
  historyList: $('history-list'),
};

let activeJobId = null;
let activeES = null;
let modelsCache = null;       // { provider, default_fast, default_smart, models: [...] }
let userModelChoice = {};     // { fast, smart, per_step: {use_cases, nfr, ...} }

const LS_KEY = 'cascade.modelChoice';

// ---------- init ----------

(async function init() {
  loadModelChoice();
  await loadHealth();
  await loadPresets();
  await loadModels();

  els.preset.addEventListener('change', onPresetChange);
  els.generate.addEventListener('click', onGenerate);
  els.download.addEventListener('click', onDownload);

  // Live cost estimate while user types
  for (const id of ['bt', 'bp', 'features']) {
    document.getElementById(id).addEventListener('input', updateCostEstimate);
  }
  updateCostEstimate();

  els.settingsBtn.addEventListener('click', openSettings);
  els.settingsClose.addEventListener('click', closeSettings);
  els.settingsModal.querySelector('.modal-backdrop').addEventListener('click', closeSettings);
  els.settingsSave.addEventListener('click', saveSettings);
  els.modelReset.addEventListener('click', resetModelChoice);
  els.modelFastSel.addEventListener('change', () => updateModelMeta('fast'));
  els.modelSmartSel.addEventListener('change', () => updateModelMeta('smart'));

  if (els.refineApply) els.refineApply.addEventListener('click', onRefineApply);
  if (els.refineComment) els.refineComment.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onRefineApply(); }
  });

  // Wave 3 wiring
  els.previewBtn.addEventListener('click', openPreview);
  els.previewClose.addEventListener('click', closePreview);
  els.previewReload.addEventListener('click', () => {
    if (els.previewFrame.src) els.previewFrame.src = els.previewFrame.src;
  });
  els.previewOpen.addEventListener('click', () => {
    if (activeJobId) window.open(`/api/jobs/${activeJobId}/app/src/index.html`, '_blank');
  });
  els.previewModal.querySelector('.modal-backdrop').addEventListener('click', closePreview);

  els.traceBtn.addEventListener('click', openTraceability);
  els.traceClose.addEventListener('click', () => { els.traceModal.hidden = true; });
  els.traceModal.querySelector('.modal-backdrop').addEventListener('click', () => { els.traceModal.hidden = true; });

  els.historyBtn.addEventListener('click', toggleHistory);
  els.historyClose.addEventListener('click', () => { els.historyPanel.hidden = true; });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !els.settingsModal.hidden) closeSettings();
  });
})();

async function loadHealth() {
  try {
    const r = await fetch('/api/health');
    const j = await r.json();
    els.health.textContent = `${j.provider} · API готов`;
    els.health.classList.add('ok');
  } catch (e) {
    els.health.textContent = 'API недоступен';
    els.health.classList.add('error');
  }
}

async function loadPresets() {
  try {
    const r = await fetch('/api/presets');
    const presets = await r.json();
    for (const p of presets) {
      const opt = document.createElement('option');
      opt.value = p.name;
      opt.textContent = p.title;
      els.preset.appendChild(opt);
    }
  } catch (e) {
    console.error('Failed to load presets', e);
  }
}

async function loadModels() {
  try {
    const r = await fetch('/api/models');
    modelsCache = await r.json();
  } catch (e) {
    console.error('Failed to load models', e);
    return;
  }
  populateModelSelect(els.modelFastSel, 'fast');
  populateModelSelect(els.modelSmartSel, 'smart');
  for (const step of STEP_NAMES) {
    const sel = document.getElementById(`model-step-${step}`);
    if (sel) populatePerStepSelect(sel, step);
  }
  updateModelMeta('fast');
  updateModelMeta('smart');
}

function populateModelSelect(selectEl, tier) {
  if (!modelsCache) return;
  selectEl.innerHTML = '';
  const chosen = userModelChoice[tier] || (tier === 'fast' ? modelsCache.default_fast : modelsCache.default_smart);
  for (const m of modelsCache.models) {
    const opt = document.createElement('option');
    opt.value = m.id;
    const tierTag = m.tier === tier ? '✓ ' : '';
    opt.textContent = `${tierTag}${m.label}  ($${m.price_in.toFixed(2)}/$${m.price_out.toFixed(2)} per M)`;
    if (m.id === chosen) opt.selected = true;
    selectEl.appendChild(opt);
  }
  if (!modelsCache.models.find(m => m.id === chosen)) {
    const opt = document.createElement('option');
    opt.value = chosen; opt.textContent = chosen; opt.selected = true;
    selectEl.prepend(opt);
  }
}

function populatePerStepSelect(selectEl, step) {
  if (!modelsCache) return;
  selectEl.innerHTML = '';
  // First option: "use tier default" (empty value)
  const noOverride = document.createElement('option');
  noOverride.value = '';
  noOverride.textContent = '— использовать tier-дефолт —';
  selectEl.appendChild(noOverride);

  const chosen = (userModelChoice.per_step || {})[step] || '';
  for (const m of modelsCache.models) {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = `${m.label}  ($${m.price_in}/$${m.price_out})`;
    if (m.id === chosen) opt.selected = true;
    selectEl.appendChild(opt);
  }
}

function updateModelMeta(tier) {
  if (!modelsCache) return;
  const sel = tier === 'fast' ? els.modelFastSel : els.modelSmartSel;
  const meta = tier === 'fast' ? els.modelFastMeta : els.modelSmartMeta;
  const id = sel.value;
  const m = modelsCache.models.find(x => x.id === id);
  if (m) {
    meta.textContent = `${m.note} · контекст ${(m.context / 1000).toFixed(0)}K · $${m.price_in}/$${m.price_out} per M`;
  } else {
    meta.textContent = id;
  }
}

function loadModelChoice() {
  try {
    userModelChoice = JSON.parse(localStorage.getItem(LS_KEY) || '{}') || {};
  } catch { userModelChoice = {}; }
  if (!userModelChoice.per_step) userModelChoice.per_step = {};
}

function persistModelChoice() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(userModelChoice)); } catch {}
}

function openSettings() {
  els.settingsModal.hidden = false;
  if (modelsCache) {
    populateModelSelect(els.modelFastSel, 'fast');
    populateModelSelect(els.modelSmartSel, 'smart');
    for (const step of STEP_NAMES) {
      const sel = document.getElementById(`model-step-${step}`);
      if (sel) populatePerStepSelect(sel, step);
    }
    updateModelMeta('fast');
    updateModelMeta('smart');
  }
}

function closeSettings() { els.settingsModal.hidden = true; }

function saveSettings() {
  userModelChoice = {
    fast: els.modelFastSel.value,
    smart: els.modelSmartSel.value,
    per_step: {},
  };
  for (const step of STEP_NAMES) {
    const sel = document.getElementById(`model-step-${step}`);
    if (sel && sel.value) userModelChoice.per_step[step] = sel.value;
  }
  persistModelChoice();
  closeSettings();
  updateCostEstimate();
}

function resetModelChoice() {
  userModelChoice = { per_step: {} };
  persistModelChoice();
  if (modelsCache) {
    populateModelSelect(els.modelFastSel, 'fast');
    populateModelSelect(els.modelSmartSel, 'smart');
    for (const step of STEP_NAMES) {
      const sel = document.getElementById(`model-step-${step}`);
      if (sel) populatePerStepSelect(sel, step);
    }
    updateModelMeta('fast');
    updateModelMeta('smart');
  }
}

async function onPresetChange() {
  const name = els.preset.value;
  if (!name) return;
  const r = await fetch(`/api/preset/${name}`);
  if (!r.ok) return;
  const p = await r.json();
  els.bt.value = p.business_requirements;
  els.bp.value = p.business_process;
  els.features.value = p.features || '';
  updateCostEstimate();
}

function updateCostEstimate() {
  if (!els.costHint || !modelsCache) return;
  const totalChars = (els.bt.value.length + els.bp.value.length + els.features.value.length);
  // Rough: 1 token ≈ 3 chars for Russian. Pipeline overhead: each step inflates input by ~3x
  // (system prompt + previous artifacts as context). Total input ≈ totalChars * 12 / 3 = 4x.
  const inputTokens = Math.round(totalChars * 4);
  // Output is roughly 80% of input across 6 steps
  const outputTokens = Math.round(inputTokens * 0.8);

  const fastId = userModelChoice.fast || modelsCache.default_fast;
  const smartId = userModelChoice.smart || modelsCache.default_smart;
  const fast = modelsCache.models.find(m => m.id === fastId);
  const smart = modelsCache.models.find(m => m.id === smartId);
  if (!fast || !smart) {
    els.costHint.textContent = `~${(inputTokens / 1000).toFixed(1)}K in / ~${(outputTokens / 1000).toFixed(1)}K out`;
    return;
  }

  // Fast handles ~70% of calls (use_cases, nfr, tests, readme), smart ~30% (fr, code)
  const fastIn = inputTokens * 0.4;
  const smartIn = inputTokens * 0.6;
  const fastOut = outputTokens * 0.5;
  const smartOut = outputTokens * 0.5;
  const cost = (
    fastIn * fast.price_in / 1e6 + fastOut * fast.price_out / 1e6 +
    smartIn * smart.price_in / 1e6 + smartOut * smart.price_out / 1e6
  );

  els.costHint.innerHTML = `Прогон ~3–5 мин · оценка ~$${cost.toFixed(3)} (${(inputTokens / 1000).toFixed(1)}K in / ${(outputTokens / 1000).toFixed(1)}K out)`;
}

// ---------- generation flow ----------

async function onGenerate() {
  const bt = els.bt.value.trim();
  const bp = els.bp.value.trim();
  const features = els.features.value.trim();
  if (bt.length < 10 || bp.length < 10) {
    alert('Заполни БТ и БП (минимум 10 символов в каждом).');
    return;
  }

  resetUI();
  els.generate.disabled = true;
  els.generate.textContent = 'Запускаю...';
  if (els.skipUC.checked) markStep('use_cases', 'skipped');
  if (els.skipTests.checked) markStep('tests', 'skipped');

  const payload = {
    business_requirements: bt,
    business_process: bp,
    features: features || null,
    skip_use_cases: els.skipUC.checked,
    skip_tests: els.skipTests.checked,
    self_check: els.selfCheck ? els.selfCheck.checked : true,
  };
  if (userModelChoice.fast) payload.model_fast = userModelChoice.fast;
  if (userModelChoice.smart) payload.model_smart = userModelChoice.smart;
  if (userModelChoice.per_step && Object.keys(userModelChoice.per_step).length) {
    payload.per_step_models = userModelChoice.per_step;
  }

  let jobId;
  try {
    const r = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      throw new Error(`HTTP ${r.status}: ${txt.slice(0, 200)}`);
    }
    const j = await r.json();
    jobId = j.id;
    activeJobId = jobId;
  } catch (e) {
    alert(`Не удалось стартовать: ${e}`);
    els.generate.disabled = false;
    els.generate.textContent = 'Сгенерировать';
    return;
  }

  els.generate.textContent = 'Идёт генерация...';
  attachStream(jobId);
}

function resetUI() {
  els.steps.forEach((li) => {
    li.classList.remove('running', 'done', 'error', 'skipped', 'rechecking', 'warning');
    li.querySelector('.step-status').textContent = '';
  });
  els.meta.textContent = '';
  els.fileTree.innerHTML = '';
  els.fileContent.innerHTML = '<code>← выбери файл слева</code>';
  els.fileContent.classList.remove('streaming');
  els.download.disabled = true;
  if (els.refinePanel) els.refinePanel.hidden = true;
}

function attachStream(jobId) {
  if (activeES) activeES.close();
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  activeES = es;

  const startTs = Date.now();
  let stepStart = null;
  let codeBuffer = '';   // accumulated streaming text for `code` step
  let isRefine = false;

  es.addEventListener('start', (e) => {
    const d = JSON.parse(e.data);
    isRefine = !!d.refinement;
    setMeta({
      'Задача': d.task,
      'Провайдер': d.provider,
      'Модели': isRefine
        ? `smart=${d.model_smart.split('/').pop()}`
        : `fast=${d.model_fast.split('/').pop()} · smart=${d.model_smart.split('/').pop()}`,
      'Шагов': d.total,
      ...(isRefine ? { 'Режим': 'доработка', 'Комментарий': d.comment } : {}),
    });
  });

  es.addEventListener('step_start', (e) => {
    markStep(JSON.parse(e.data).step, 'running');
    stepStart = Date.now();
  });

  es.addEventListener('step_done', (e) => {
    const d = JSON.parse(e.data);
    const elapsed = stepStart ? ((Date.now() - stepStart) / 1000).toFixed(1) : '';
    markStep(d.step, 'done', elapsed ? `${elapsed}s` : '');
    if (d.step === 'code') {
      els.fileContent.classList.remove('streaming');
      codeBuffer = '';
    }
  });

  // Live streaming chunks during code generation
  es.addEventListener('step_chunk', (e) => {
    const d = JSON.parse(e.data);
    if (d.step !== 'code') return;
    codeBuffer = d.text || (codeBuffer + (d.piece || ''));
    showLiveCode(codeBuffer);
  });

  // Self-check events
  es.addEventListener('self_check_retry', (e) => {
    const d = JSON.parse(e.data);
    const li = document.querySelector(`#steps li[data-step="${d.step}"]`);
    if (!li) return;
    li.classList.add('rechecking');
    li.querySelector('.step-status').textContent = `↻ ${d.attempt}: ${(d.missing || []).slice(0,3).join(', ')}`;
  });
  es.addEventListener('self_check_pass', (e) => {
    const d = JSON.parse(e.data);
    const li = document.querySelector(`#steps li[data-step="${d.step}"]`);
    if (li) li.classList.remove('rechecking');
  });
  es.addEventListener('self_check_fail', (e) => {
    const d = JSON.parse(e.data);
    const li = document.querySelector(`#steps li[data-step="${d.step}"]`);
    if (!li) return;
    li.classList.remove('rechecking');
    li.classList.add('warning');
    li.querySelector('.step-status').textContent = `⚠ missing: ${(d.missing || []).slice(0,2).join(',')}`;
  });

  es.addEventListener('done', (e) => {
    const d = JSON.parse(e.data);
    const elapsed = ((Date.now() - startTs) / 1000).toFixed(1);
    setMeta({
      'Готово за': `${elapsed} с`,
      'Файлов': d.files,
      'Вызовов LLM': d.calls,
      'Tokens in': d.input_tokens.toLocaleString('ru-RU'),
      'Tokens out': d.output_tokens.toLocaleString('ru-RU'),
      ...(d.refinement ? { 'Режим': 'доработка' } : {}),
    });
    finishJob(jobId);
  });

  es.addEventListener('error', (e) => {
    let payload = {};
    try { payload = JSON.parse(e.data || '{}'); } catch {}
    if (payload && payload.error) {
      const running = document.querySelector('.steps li.running');
      if (running) {
        running.classList.remove('running');
        running.classList.add('error');
      }
      els.meta.innerHTML = `<span style="color: var(--danger)">Ошибка: ${escapeHtml(payload.error)}</span>`;
      finishJob(jobId, true);
    }
  });

  es.addEventListener('stream_end', () => {
    es.close();
    activeES = null;
  });
}

function showLiveCode(text) {
  // Show streaming text in the file viewer pane with a special class
  els.fileContent.classList.add('streaming');
  els.fileContent.innerHTML = `<code>${escapeHtml(text)}<span class="caret"></span></code>`;
  // Auto-scroll to bottom while streaming
  els.fileContent.scrollTop = els.fileContent.scrollHeight;
  // Hint in tree
  if (!els.fileTree.querySelector('li[data-streaming="1"]')) {
    const li = document.createElement('li');
    li.dataset.path = '__streaming';
    li.dataset.streaming = '1';
    li.dataset.icon = '⚡';
    li.innerHTML = `<span class="filename">генерация кода…</span><span class="size">live</span>`;
    li.classList.add('active');
    els.fileTree.querySelectorAll('li').forEach((x) => x.classList.remove('active'));
    els.fileTree.prepend(li);
  }
}

function markStep(name, state, status = '') {
  const li = document.querySelector(`#steps li[data-step="${name}"]`);
  if (!li) return;
  li.classList.remove('running', 'done', 'error', 'skipped', 'rechecking', 'warning');
  li.classList.add(state);
  if (status) li.querySelector('.step-status').textContent = status;
}

function setMeta(obj) {
  els.meta.innerHTML = Object.entries(obj)
    .map(([k, v]) => `<span><b>${escapeHtml(k)}:</b> ${escapeHtml(String(v))}</span>`)
    .join('');
}

async function finishJob(jobId, isError = false) {
  els.generate.disabled = false;
  els.generate.textContent = 'Сгенерировать';
  if (isError) return;
  els.download.disabled = false;
  els.previewBtn.disabled = false;
  els.traceBtn.disabled = false;
  await loadFiles(jobId);
  // Show refinement panel
  if (els.refinePanel) {
    els.refinePanel.hidden = false;
    els.refineComment.value = '';
  }
}

// ---------- Wave 3: preview / traceability / history ----------

function openPreview() {
  if (!activeJobId) return;
  els.previewFrame.src = `/api/jobs/${activeJobId}/app/src/index.html`;
  els.previewModal.hidden = false;
}
function closePreview() {
  els.previewModal.hidden = true;
  els.previewFrame.src = 'about:blank';
}

async function openTraceability() {
  if (!activeJobId) return;
  els.traceBody.innerHTML = '<div class="loading">Загрузка матрицы...</div>';
  els.traceModal.hidden = false;
  try {
    const r = await fetch(`/api/jobs/${activeJobId}/traceability`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    renderTraceability(data);
  } catch (e) {
    els.traceBody.innerHTML = `<div class="loading" style="color: var(--danger)">Ошибка: ${escapeHtml(String(e))}</div>`;
  }
}

function renderTraceability(data) {
  const t = data.totals;
  const fr_ok_pct = t.fr_total ? Math.round(100 * t.fr_implemented / t.fr_total) : 0;

  let html = `
    <div class="trace-summary">
      <div class="stat"><b>${t.bt_total}</b><span>БТ всего</span></div>
      <div class="stat"><b>${t.bt_required}</b><span>обязательных</span></div>
      <div class="stat"><b>${t.uc_total}</b><span>юз-кейсов</span></div>
      <div class="stat"><b>${t.fr_total}</b><span>ФТ</span></div>
      <div class="stat ${fr_ok_pct === 100 ? 'ok' : 'warn'}"><b>${t.fr_implemented}/${t.fr_total}</b><span>ФТ → @implements (${fr_ok_pct}%)</span></div>
    </div>

    <h4 class="trace-h">БТ → юз-кейсы → ФТ</h4>
    <table class="trace-table">
      <thead><tr><th>БТ</th><th>обяз.</th><th>UC</th><th>ФТ</th></tr></thead>
      <tbody>
        ${data.bt_rows.map(r => `
          <tr class="${r.ucs.length === 0 && r.frs.length === 0 ? 'row-empty' : ''}">
            <td><code>${r.bt}</code></td>
            <td>${r.required ? '<span class="pill required">обяз.</span>' : '<span class="pill">опц.</span>'}</td>
            <td>${r.ucs.map(u => `<code>${u}</code>`).join(' ') || '<span class="muted">—</span>'}</td>
            <td>${r.frs.map(f => `<code>${f}</code>`).join(' ') || '<span class="muted muted-warn">— нет ФТ</span>'}</td>
          </tr>`).join('')}
      </tbody>
    </table>

    <h4 class="trace-h">ФТ → файлы (через @implements)</h4>
    <table class="trace-table">
      <thead><tr><th>ФТ</th><th>статус</th><th>файлы</th></tr></thead>
      <tbody>
        ${data.fr_rows.map(r => `
          <tr>
            <td><code>${r.fr}</code></td>
            <td>${r.implemented
              ? '<span class="pill ok">✓ implements</span>'
              : '<span class="pill warn">⚠ missing</span>'}</td>
            <td>${r.files.map(f => `<code>${escapeHtml(f)}</code>`).join(' ') || '<span class="muted muted-warn">не найдено</span>'}</td>
          </tr>`).join('')}
      </tbody>
    </table>
  `;
  els.traceBody.innerHTML = html;
}

async function toggleHistory() {
  if (!els.historyPanel.hidden) {
    els.historyPanel.hidden = true;
    return;
  }
  els.historyList.innerHTML = '<li class="loading">Загрузка...</li>';
  els.historyPanel.hidden = false;
  try {
    const r = await fetch('/api/jobs');
    const items = await r.json();
    if (!items.length) {
      els.historyList.innerHTML = '<li class="empty">Нет сохранённых генераций.</li>';
      return;
    }
    els.historyList.innerHTML = items.map(item => `
      <li data-id="${item.id}" class="history-item ${item.status}">
        <div class="hi-main">
          <span class="hi-status ${item.status}"></span>
          <span class="hi-task">${escapeHtml(item.task)}</span>
          <span class="hi-files">${item.files_count || 0} файлов</span>
        </div>
        <div class="hi-actions">
          <button data-action="open" class="hi-btn">Открыть</button>
          <button data-action="delete" class="hi-btn hi-btn-danger">×</button>
        </div>
      </li>
    `).join('');
    els.historyList.querySelectorAll('.history-item').forEach(li => {
      li.querySelector('[data-action="open"]').addEventListener('click', () => loadHistoryJob(li.dataset.id));
      li.querySelector('[data-action="delete"]').addEventListener('click', () => deleteHistoryJob(li.dataset.id));
    });
  } catch (e) {
    els.historyList.innerHTML = `<li class="empty">Ошибка: ${escapeHtml(String(e))}</li>`;
  }
}

async function loadHistoryJob(jobId) {
  resetUI();
  activeJobId = jobId;
  els.historyPanel.hidden = true;
  els.download.disabled = false;
  els.previewBtn.disabled = false;
  els.traceBtn.disabled = false;
  // Replay events from saved history
  try {
    const r = await fetch(`/api/jobs/${jobId}`);
    const job = await r.json();
    for (const ev of (job.events || [])) {
      if (ev.type === 'start') setMeta({ 'Задача': ev.task, 'Провайдер': ev.provider, 'Шагов': ev.total });
      if (ev.type === 'step_done') markStep(ev.step, 'done');
      if (ev.type === 'self_check_fail') markStep(ev.step, 'warning', 'missing');
    }
    if (els.refinePanel) els.refinePanel.hidden = false;
  } catch {}
  await loadFiles(jobId);
}

async function deleteHistoryJob(jobId) {
  if (!confirm('Удалить эту генерацию со всеми файлами?')) return;
  await fetch(`/api/jobs/${jobId}`, { method: 'DELETE' });
  await toggleHistory(); await toggleHistory();  // refresh
}

function fileIcon(path) {
  if (path.endsWith('.html')) return '🌐';
  if (path.endsWith('.css')) return '🎨';
  if (path.endsWith('.test.js')) return '🧪';
  if (path.endsWith('.js')) return '📜';
  if (path.endsWith('.md')) {
    if (path.includes('functional-req')) return '📐';
    if (path.includes('non-functional')) return '⚡';
    if (path.includes('use-cases')) return '👤';
    if (path.includes('README')) return '📖';
    if (path.includes('_generator_log')) return '📊';
    return '📄';
  }
  if (path.endsWith('.json')) return '📦';
  return '📄';
}

async function loadFiles(jobId) {
  const r = await fetch(`/api/jobs/${jobId}/files`);
  const j = await r.json();
  els.fileTree.innerHTML = '';
  for (const f of j.files) {
    const li = document.createElement('li');
    li.dataset.path = f.path;
    li.dataset.icon = fileIcon(f.path);
    li.innerHTML = `<span class="filename">${escapeHtml(f.path)}</span><span class="size">${formatSize(f.size)}</span>`;
    li.addEventListener('click', () => selectFile(jobId, li));
    els.fileTree.appendChild(li);
  }
  const auto = j.files.find((f) => f.path.endsWith('src/index.html'))
    || j.files.find((f) => f.path.endsWith('functional-req.md'))
    || j.files[0];
  if (auto) {
    const li = els.fileTree.querySelector(`li[data-path="${cssEscape(auto.path)}"]`);
    if (li) selectFile(jobId, li);
  }
}

async function selectFile(jobId, li) {
  els.fileTree.querySelectorAll('li').forEach((x) => x.classList.remove('active'));
  li.classList.add('active');
  els.fileContent.classList.remove('streaming');
  const path = li.dataset.path;
  const r = await fetch(`/api/jobs/${jobId}/file?path=${encodeURIComponent(path)}`);
  const text = await r.text();
  els.fileContent.innerHTML = `<code>${escapeHtml(text)}</code>`;
  els.fileContent.scrollTop = 0;
}

function onDownload() {
  if (!activeJobId) return;
  window.location.href = `/api/jobs/${activeJobId}/zip`;
}

// ---------- refinement ----------

async function onRefineApply() {
  if (!activeJobId) return;
  const comment = els.refineComment.value.trim();
  if (comment.length < 3) {
    alert('Опиши доработку чуть подробнее (от 3 символов).');
    return;
  }
  els.refineApply.disabled = true;
  els.refineApply.textContent = 'Применяю...';

  const payload = { comment };
  if (userModelChoice.smart) payload.model_smart = userModelChoice.smart;

  try {
    const r = await fetch(`/api/jobs/${activeJobId}/refine`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) {
      const txt = await r.text();
      throw new Error(`HTTP ${r.status}: ${txt.slice(0, 200)}`);
    }
    // Reset progress UI for the refine run
    els.steps.forEach((li) => {
      li.classList.remove('running', 'done', 'error', 'skipped', 'rechecking', 'warning');
      li.querySelector('.step-status').textContent = '';
    });
    attachStream(activeJobId);
  } catch (e) {
    alert(`Не удалось применить: ${e}`);
  } finally {
    els.refineApply.disabled = false;
    els.refineApply.textContent = 'Применить';
  }
}

// ---------- helpers ----------

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function cssEscape(s) { return String(s).replace(/(["\\])/g, '\\$1'); }
function formatSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}
