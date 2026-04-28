// Cascade — frontend logic.
// Single-page app: load presets/models, run jobs, stream SSE progress, view files.

const $ = (id) => document.getElementById(id);

const els = {
  preset: $('preset-select'),
  bt: $('bt'),
  bp: $('bp'),
  features: $('features'),
  skipUC: $('opt-skip-uc'),
  skipTests: $('opt-skip-tests'),
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
};

let activeJobId = null;
let activeES = null;
let modelsCache = null;       // { provider, default_fast, default_smart, models: [...] }
let userModelChoice = {};     // { fast, smart } from localStorage

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

  els.settingsBtn.addEventListener('click', openSettings);
  els.settingsClose.addEventListener('click', closeSettings);
  els.settingsModal.querySelector('.modal-backdrop').addEventListener('click', closeSettings);
  els.settingsSave.addEventListener('click', saveSettings);
  els.modelReset.addEventListener('click', resetModelChoice);
  els.modelFastSel.addEventListener('change', () => updateModelMeta('fast'));
  els.modelSmartSel.addEventListener('change', () => updateModelMeta('smart'));

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
  // If chosen not in list (custom model), add as first option
  if (!modelsCache.models.find(m => m.id === chosen)) {
    const opt = document.createElement('option');
    opt.value = chosen;
    opt.textContent = chosen;
    opt.selected = true;
    selectEl.prepend(opt);
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
}

function persistModelChoice() {
  try { localStorage.setItem(LS_KEY, JSON.stringify(userModelChoice)); } catch {}
}

function openSettings() {
  els.settingsModal.hidden = false;
  // Re-sync selectors with current choice
  if (modelsCache) {
    populateModelSelect(els.modelFastSel, 'fast');
    populateModelSelect(els.modelSmartSel, 'smart');
    updateModelMeta('fast');
    updateModelMeta('smart');
  }
}

function closeSettings() {
  els.settingsModal.hidden = true;
}

function saveSettings() {
  userModelChoice = {
    fast: els.modelFastSel.value,
    smart: els.modelSmartSel.value,
  };
  persistModelChoice();
  closeSettings();
}

function resetModelChoice() {
  userModelChoice = {};
  persistModelChoice();
  if (modelsCache) {
    populateModelSelect(els.modelFastSel, 'fast');
    populateModelSelect(els.modelSmartSel, 'smart');
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
  };
  if (userModelChoice.fast) payload.model_fast = userModelChoice.fast;
  if (userModelChoice.smart) payload.model_smart = userModelChoice.smart;

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
    li.classList.remove('running', 'done', 'error', 'skipped');
    li.querySelector('.step-status').textContent = '';
  });
  els.meta.textContent = '';
  els.fileTree.innerHTML = '';
  els.fileContent.innerHTML = '<code>← выбери файл слева</code>';
  els.download.disabled = true;
}

function attachStream(jobId) {
  if (activeES) activeES.close();
  const es = new EventSource(`/api/jobs/${jobId}/stream`);
  activeES = es;

  const startTs = Date.now();
  let stepStart = null;

  es.addEventListener('start', (e) => {
    const d = JSON.parse(e.data);
    setMeta({
      'Задача': d.task,
      'Провайдер': d.provider,
      'Модели': `fast=${d.model_fast.split('/').pop()} · smart=${d.model_smart.split('/').pop()}`,
      'Шагов': d.total,
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
    });
    finishJob(jobId);
  });

  es.addEventListener('error', (e) => {
    let payload = {};
    try { payload = JSON.parse(e.data || '{}'); } catch {}
    if (payload && payload.error) {
      // mark current running step as error
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

function markStep(name, state, status = '') {
  const li = document.querySelector(`#steps li[data-step="${name}"]`);
  if (!li) return;
  li.classList.remove('running', 'done', 'error', 'skipped');
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
  await loadFiles(jobId);
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

// ---------- helpers ----------

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function cssEscape(s) {
  return String(s).replace(/(["\\])/g, '\\$1');
}

function formatSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}
