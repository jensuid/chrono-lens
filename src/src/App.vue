<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { getJson } from './api.js'
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

function selectDataset(id) {
  const found = datasets.value.find((d) => d.id === id)
  if (found) {
    dataset.value = found
    if (view.value === 'import') view.value = 'explore'
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

      <div v-if="!backendReady && backendError" class="error">{{ backendError }}</div>
      <div v-else-if="!backendReady" class="loading"><span class="spinner"></span> starting backend…</div>

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

      <div class="datasets" v-if="backendReady">
        <label>Datasets</label>
        <ul>
          <li
            v-for="d in datasets"
            :key="d.id"
            :class="{ selected: dataset && dataset.id === d.id }"
            @click="selectDataset(d.id)"
          >
            {{ d.timeRange.column }} · {{ d.rows }} rows
            <small>{{ new Date(d.timeRange.first).toLocaleDateString() }} – {{ new Date(d.timeRange.last).toLocaleDateString() }}</small>
          </li>
        </ul>
      </div>
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
    <footer class="hint-footer">
      <a @click.prevent="toggleDebug">diagnostics (⌘⇧D)</a>
    </footer>
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
h1 { font-size: 20px; margin: 0; letter-spacing: 0.5px; }
.tagline { margin: 2px 0 0; color: var(--accent); font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; }
nav { display: flex; flex-direction: column; gap: 6px; }
nav button { text-align: left; width: 100%; }
nav button.active { border-color: var(--accent); color: var(--accent); }
nav button.disabled { opacity: 0.45; }
.datasets ul { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.datasets li {
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  display: flex; flex-direction: column; gap: 2px;
}
.datasets li.selected { border-color: var(--accent); }
.datasets small { color: var(--muted); font-size: 11px; }
.loading { color: var(--muted); display: flex; gap: 8px; align-items: center; }
.hint-footer { margin-top: auto; font-size: 11px; }
.hint-footer a { color: var(--muted); cursor: pointer; text-decoration: underline dotted; }
main { flex: 1; overflow-y: auto; padding: 20px 24px; }
</style>
