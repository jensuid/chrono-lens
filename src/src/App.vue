<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { getJson, deleteDataset } from './api.js'
import { getLog } from './debug.js'
import ImportView from './views/ImportView.vue'
import ExploreView from './views/ExploreView.vue'
import DecomposeView from './views/DecomposeView.vue'
import ForecastView from './views/ForecastView.vue'
import AnomaliesView from './views/AnomaliesView.vue'
import DebugConsole from './components/DebugConsole.vue'

// Current dataset metadata (null until one is imported/selected).
const dataset = ref(null)
const datasets = ref([])
const view = ref('import')
const backendReady = ref(false)
const backendError = ref('')
const showDebug = ref(false)
const dbg = ref(null)

function toggleDebug() {
  showDebug.value = !showDebug.value
}

const views = [
  { id: 'import', label: 'Import', component: ImportView },
  { id: 'explore', label: 'Explore', component: ExploreView },
  { id: 'decompose', label: 'Decompose', component: DecomposeView },
  { id: 'forecast', label: 'Forecast', component: ForecastView },
  { id: 'anomalies', label: 'Anomalies', component: AnomaliesView },
]

async function refreshDatasets() {
  datasets.value = await getJson('/api/datasets')
}

function onImported(meta) {
  dataset.value = meta
  view.value = 'explore'
  refreshDatasets()
}

async function selectDataset(id) {
  // List entries are summary-only; fetch full metadata (columns, dtypes,
  // missing) so the analysis views get everything they need.
  try {
    dataset.value = await getJson(`/api/datasets/${id}`)
    if (view.value === 'import') view.value = 'explore'
  } catch (e) {
    // Stale list entry (deleted on disk): drop it.
    datasets.value = datasets.value.filter((x) => x.id !== id)
  }
}

// Two-step inline delete: WKWebView in the packaged app never shows
// native confirm()/alert() dialogs (silent no-ops), so deletion confirms
// in-app — first click arms the button, second click deletes; clicking
// anywhere else disarms.
const pendingDeleteId = ref(null)
const deleteError = ref('')

function armDelete(d) {
  pendingDeleteId.value = d.id
  deleteError.value = ''
}

async function removeDataset(d) {
  try {
    await deleteDataset(d.id)
    datasets.value = datasets.value.filter((x) => x.id !== d.id)
    pendingDeleteId.value = null
    if (dataset.value?.id === d.id) {
      dataset.value = null
      view.value = 'import'
    }
  } catch (e) {
    deleteError.value = `Could not delete "${d.name || d.id}": ${e.message}`
  }
}

async function waitForBackend() {
  // The sidecar takes ~25-60s to unpack on first launch; poll until it
  // answers rather than showing a permanent error on the first failed
  // health check.
  const deadline = Date.now() + 120_000
  let lastError = null
  while (Date.now() < deadline) {
    try {
      await getJson('/api/health')
      return
    } catch (e) {
      lastError = e
      await new Promise((r) => setTimeout(r, 2000))
    }
  }
  throw lastError ?? new Error('timed out')
}

function onKeydown(e) {
  // Cmd/Ctrl+Shift+D toggles the diagnostics console.
  if (e.key.toLowerCase() === 'd' && e.shiftKey && (e.metaKey || e.ctrlKey)) {
    e.preventDefault()
    toggleDebug()
  }
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    await waitForBackend()
    backendReady.value = true
    await refreshDatasets()
  } catch (e) {
    backendError.value = `backend not reachable: ${e.message}`
  }
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="shell">
    <aside>
      <header>
        <h1>ChronoLens</h1>
        <p class="tagline">time series analysis</p>
      </header>

      <div v-if="backendReady && backendError" class="error">{{ backendError }}</div>

      <nav>
        <button
          v-for="v in views"
          :key="v.id"
          :class="{ active: view === v.id, disabled: v.id !== 'import' && !dataset }"
          @click="dataset || v.id === 'import' ? (view = v.id) : null"
        >
          {{ v.label }}
        </button>
      </nav>

      <div class="datasets" v-if="backendReady" @click="pendingDeleteId = null">
        <label>Datasets</label>
        <ul>
          <li
            v-for="d in datasets"
            :key="d.id"
            :class="{ selected: dataset && dataset.id === d.id, armed: pendingDeleteId === d.id }"
            @click.stop="pendingDeleteId === d.id || selectDataset(d.id)"
          >
            <div class="drow" :title="d.name || d.id">
              <span class="dname">{{ d.name || d.id }}</span>
              <small>{{ d.rows }} rows · {{ new Date(d.timeRange.first).toLocaleDateString() }} – {{ new Date(d.timeRange.last).toLocaleDateString() }}</small>
            </div>
            <template v-if="pendingDeleteId === d.id">
              <button class="del confirm" @click.stop="removeDataset(d)">delete</button>
              <button class="del cancel" @click.stop="pendingDeleteId = null">cancel</button>
            </template>
            <button
              v-else
              class="del"
              :title="`Delete ${d.name || d.id}`"
              @click.stop="armDelete(d)"
            >✕</button>
          </li>
        </ul>
        <p v-if="deleteError" class="error small">{{ deleteError }}</p>
        <p v-if="!datasets.length" class="none-yet">no datasets imported yet</p>
      </div>

      <footer class="side-footer">
        <span class="status-dot" :class="backendReady ? 'ok' : 'busy'" title="backend status"></span>
        <a @click.prevent="toggleDebug">diagnostics (⌘⇧D)</a>
      </footer>
    </aside>

    <main>
      <component
        :is="views.find((v) => v.id === view).component"
        :dataset="dataset"
        :backend-ready="backendReady"
        @imported="onImported"
      />
    </main>

    <DebugConsole :open="showDebug" @close="showDebug = false" />
  </div>
</template>

<style scoped>
.shell { display: flex; height: 100%; }
aside {
  width: 230px;
  background: var(--panel);
  border-right: 1px solid var(--border);
  padding: 16px 14px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  overflow-y: auto;
}
h1 {
  font-size: 20px; margin: 0; letter-spacing: 0.5px;
  color: var(--accent);
}
.tagline { margin: 2px 0 0; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }
nav { display: flex; flex-direction: column; gap: 6px; }
nav button { text-align: left; width: 100%; }
nav button.active { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }
nav button.disabled { opacity: 0.45; }
.datasets ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.datasets li {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.datasets li.selected { border-color: var(--accent); }
.datasets .drow { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.datasets .dname { font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.datasets small { color: var(--muted); font-size: 11px; }
.datasets .del {
  flex: none;
  border: none; background: none; color: var(--muted);
  font-size: 12px; padding: 2px 5px; line-height: 1; border-radius: 4px;
}
.datasets li.armed { border-color: var(--danger); background: #fff5f7; }
.datasets .del:hover { color: var(--danger); background: #ffe4e9; border: none; }
.datasets .del.confirm {
  background: var(--danger); color: #fff; border: none;
  font-size: 11px; padding: 3px 8px;
}
.datasets .del.confirm:hover { background: #be123c; color: #fff; }
.datasets .del.cancel { font-size: 11px; padding: 3px 6px; }
.datasets .none-yet { color: var(--muted); font-size: 12px; margin: 4px 0 0; }
.error.small { font-size: 12px; padding: 6px 8px; margin: 6px 0 0; }
.loading { color: var(--muted); display: flex; gap: 8px; align-items: center; }
.side-footer {
  margin-top: auto;               /* pins to the sidebar bottom */
  display: flex; align-items: center; gap: 8px;
  padding-top: 12px; border-top: 1px solid var(--border);
  font-size: 11px;
}
.side-footer a { color: var(--muted); cursor: pointer; text-decoration: underline dotted; }
.side-footer a:hover { color: var(--accent); }
.status-dot {
  width: 8px; height: 8px; border-radius: 50%; flex: none;
}
.status-dot.ok { background: var(--ok); }
.status-dot.busy {
  background: var(--accent-2);
  animation: pulse 1.2s ease-in-out infinite;
}
.status-dot.err { background: var(--danger); }
@keyframes pulse { 50% { opacity: 0.25; } }
main { flex: 1; overflow-y: auto; padding: 20px 24px; }
</style>
