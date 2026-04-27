// Frontend logic for the autonomous generator UI.
// State machine: idle → submitting → running → done/error

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
};

let activeJobId = null;
let activeES = null;

// ---------- init ----------

(async function init() {
  await loadHealth();
  await loadPresets();
  els.preset.addEventListener('change', onPresetChange);
  els.generate.addEventListener('click', onGenerate);
  els.download.addEventListener('click', onDownload);
})();

async function loadHealth() {
  try {
    const r = await fetch('/api/health');
    const j = await r.json();
    els.health.textContent = `${j.provider} · ${j.model_fast} + ${j.model_smart}`;
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

  // Reset UI state
  resetUI();
  els.generate.disabled = true;
  els.generate.textContent = 'Запускаю...';
  // Mark skipped steps grey upfront
  if (els.skipUC.checked) markStep('use_cases', 'skipped');
  if (els.skipTests.checked) markStep('tests', 'skipped');

  let jobId;
  try {
    const r = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        business_requirements: bt,
        business_process: bp,
        features: features || null,
        skip_use_cases: els.skipUC.checked,
        skip_tests: els.skipTests.checked,
      }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();
    jobId = j.id;
    activeJobId = jobId;
  } catch (e) {
    alert(`Не удалось стартовать: ${e}`);
    els.generate.disabled = false;
    els.generate.textContent = 'Сгенерировать →';
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
      'Провайдер': `${d.provider} (${d.model_fast} + ${d.model_smart})`,
      'Шагов': d.total,
    });
  });

  es.addEventListener('step_start', (e) => {
    const d = JSON.parse(e.data);
    markStep(d.step, 'running');
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
    if (payload.error) {
      const idx = +payload?.index;
      if (idx) {
        const step = els.steps[idx - 1];
        if (step) step.classList.add('error');
      }
      els.meta.innerHTML = `<span style="color: var(--danger)">Ошибка: ${escapeHtml(payload.error)}</span>`;
      finishJob(jobId, true);
    }
    // Native browser EventSource error (connection lost) → just log
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
  els.generate.textContent = 'Сгенерировать →';
  if (isError) return;
  els.download.disabled = false;
  await loadFiles(jobId);
}

function fileIcon(path) {
  if (path.endsWith('.html')) return '🌐';
  if (path.endsWith('.css')) return '🎨';
  if (path.endsWith('.js')) return '📜';
  if (path.endsWith('.test.js')) return '🧪';
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
  // Auto-select first file (preferably src/index.html)
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
  // basic CSS attr selector escape
  return String(s).replace(/(["\\])/g, '\\$1');
}

function formatSize(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1048576).toFixed(2)} MB`;
}
