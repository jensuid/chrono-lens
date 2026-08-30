<script setup>
// Anomalies view: method + threshold, chart with red markers, table.
import { computed, reactive, ref, watch } from 'vue'
import { postJson } from '../api.js'
import TimeChart from '../components/TimeChart.vue'
import { lineChartOption, lineSeries, scatterSeries } from '../components/chartOptions.js'

const props = defineProps({ dataset: { type: Object, default: null } })

const column = ref('')
const error = ref('')
const loading = ref(false)
const result = ref(null)

const params = reactive({
  method: 'zscore',
  threshold: 4,
  window: 14,
  period: 7,
})

const needsWindow = computed(() => params.method === 'zscore')
const needsPeriod = computed(() => params.method === 'stl')

const chartOption = computed(() => {
  if (!result.value) return {}
  // Base series comes from the preview fetch.
  const base = previewPoints.value.map((r) => [
    r[props.dataset.datetimeColumn],
    r[column.value],
  ])
  return lineChartOption([
    { name: column.value, type: 'line', showSymbol: false, data: base, lineStyle: { opacity: 0.85 } },
    scatterSeries('anomalies', result.value.anomalies, {
      itemStyle: { color: '#e11d48' },
      symbolSize: 10,
    }),
  ])
})

const previewPoints = ref([])

watch(
  () => props.dataset?.id,
  async (id) => {
    result.value = null
    previewPoints.value = []
    column.value = props.dataset?.numericColumns[0] ?? ''
    if (!id) return
    try {
      const { getJson } = await import('../api.js')
      const preview = await getJson(`/api/datasets/${id}/preview?limit=100000`)
      previewPoints.value = preview.rows
    } catch {
      /* chart base is best-effort */
    }
  },
  { immediate: true },
)

async function run() {
  if (!props.dataset || !column.value) return
  error.value = ''
  loading.value = true
  try {
    result.value = await postJson(`/api/datasets/${props.dataset.id}/anomalies`, {
      column: column.value,
      method: params.method,
      threshold: params.threshold,
      ...(needsWindow.value ? { window: params.window } : {}),
      ...(needsPeriod.value ? { period: params.period } : {}),
    })
  } catch (e) {
    error.value = e.message
    result.value = null
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="anomalies" v-if="dataset">
    <div class="toolbar">
      <div>
        <label>value column</label>
        <select v-model="column">
          <option v-for="c in dataset.numericColumns" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label>method</label>
        <select v-model="params.method">
          <option value="zscore">rolling z-score</option>
          <option value="iqr">IQR fence</option>
          <option value="stl">STL residual</option>
        </select>
      </div>
      <div>
        <label>threshold: {{ params.threshold }}</label>
        <input v-model.number="params.threshold" type="range" min="0.5" max="8" step="0.25" />
      </div>
      <div v-if="needsWindow">
        <label>window</label>
        <input v-model.number="params.window" type="number" min="3" style="width: 80px" />
      </div>
      <div v-if="needsPeriod">
        <label>period</label>
        <input v-model.number="params.period" type="number" min="2" style="width: 80px" />
      </div>
      <div style="align-self: flex-end">
        <button class="primary" :disabled="loading" @click="run">
          <span v-if="loading" class="spinner"></span> detect
        </button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <TimeChart v-if="result" :option="chartOption" height="400px" />

    <div v-if="result" class="card table-card">
      <h3>{{ result.anomalies.length }} anomalies found <small v-if="result.fenceLow != null">fences [{{ result.fenceLow.toFixed(1) }}, {{ result.fenceHigh.toFixed(1) }}]</small></h3>
      <table class="data" v-if="result.anomalies.length">
        <thead>
          <tr><th>timestamp</th><th>value</th></tr>
        </thead>
        <tbody>
          <tr v-for="(a, i) in result.anomalies" :key="i">
            <td>{{ new Date(a.t).toLocaleString() }}</td>
            <td>{{ a.v?.toFixed(3) ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else class="none">none at this threshold</p>
    </div>
  </div>
  <div v-else class="empty">import a dataset first</div>
</template>

<style scoped>
.anomalies { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; gap: 22px; flex-wrap: wrap; align-items: flex-end; }
.table-card h3 { margin: 0 0 10px; font-size: 14px; }
.table-card small { color: var(--muted); font-weight: 400; margin-left: 8px; }
.none { color: var(--muted); margin: 0; }
.empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
