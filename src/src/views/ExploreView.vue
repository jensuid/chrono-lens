<script setup>
// Explore view: full-series chart, stats, missing report, resample + rolling.
import { computed, reactive, ref, watch } from 'vue'
import { getJson, postJson } from '../api.js'
import TimeChart from '../components/TimeChart.vue'
import { lineChartOption, lineSeries } from '../components/chartOptions.js'

const props = defineProps({ dataset: { type: Object, default: null } })

const column = ref('')
const error = ref('')
const loading = ref(false)

const stats = ref(null)
const resample = reactive({ freq: 'W', agg: 'mean', points: null })
const rolling = reactive({ window: 7, stat: 'mean', points: null })

const preview = ref(null)

const chartOption = computed(() => {
  const series = []
  if (preview.value) {
    const rows = preview.value.rows.map((r) => [
      r[preview.value.datetimeColumn ?? props.dataset.datetimeColumn],
      r[column.value],
    ])
    series.push({ name: column.value, type: 'line', showSymbol: false, data: rows })
  }
  if (resample.points) series.push(lineSeries(`resampled (${resample.freq}/${resample.agg})`, resample.points))
  if (rolling.points) series.push(lineSeries(`rolling ${rolling.window}·${rolling.stat}`, rolling.points))
  return lineChartOption(series)
})

watch(
  () => props.dataset?.id,
  async (id) => {
    stats.value = null
    resample.points = null
    rolling.points = null
    preview.value = null
    if (!id) return
    column.value = props.dataset.numericColumns[0] ?? ''
    await reload()
  },
  { immediate: true },
)

async function reload() {
  if (!props.dataset || !column.value) return
  error.value = ''
  loading.value = true
  try {
    // Full series via preview endpoint (all rows for the chart).
    preview.value = await getJson(`/api/datasets/${props.dataset.id}/preview?limit=100000`)
    stats.value = await postJson(`/api/datasets/${props.dataset.id}/stats`, { column: column.value })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function runResample() {
  if (!props.dataset) return
  try {
    const body = await postJson(`/api/datasets/${props.dataset.id}/resample`, {
      column: column.value,
      freq: resample.freq,
      agg: resample.agg,
    })
    resample.points = body.points
  } catch (e) {
    error.value = e.message
  }
}

async function runRolling() {
  if (!props.dataset) return
  try {
    const body = await postJson(`/api/datasets/${props.dataset.id}/rolling`, {
      column: column.value,
      window: rolling.window,
      stat: rolling.stat,
    })
    rolling.points = body.points
  } catch (e) {
    error.value = e.message
  }
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: 3 })
}
</script>

<template>
  <div class="explore" v-if="dataset">
    <div class="toolbar">
      <div>
        <label>value column</label>
        <select v-model="column" @change="reload">
          <option v-for="c in dataset.numericColumns" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label>resample</label>
        <div class="inline">
          <select v-model="resample.freq">
            <option value="H">hourly</option>
            <option value="D">daily</option>
            <option value="W">weekly</option>
            <option value="M">monthly</option>
            <option value="Q">quarterly</option>
          </select>
          <select v-model="resample.agg">
            <option value="mean">mean</option>
            <option value="sum">sum</option>
            <option value="max">max</option>
            <option value="min">min</option>
          </select>
          <button @click="runResample">apply</button>
        </div>
      </div>
      <div>
        <label>rolling window</label>
        <div class="inline">
          <input v-model.number="rolling.window" type="number" min="2" max="10000" style="width: 84px" />
          <select v-model="rolling.stat">
            <option value="mean">mean</option>
            <option value="std">std</option>
            <option value="min">min</option>
            <option value="max">max</option>
          </select>
          <button @click="runRolling">apply</button>
        </div>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <TimeChart :option="chartOption" height="420px" />

    <div class="cards" v-if="stats">
      <div class="card stat" v-for="(v, k) in stats.stats" :key="k">
        <div class="k">{{ k }}</div>
        <div class="v">{{ fmt(v) }}</div>
      </div>
      <div class="card stat">
        <div class="k">missing</div>
        <div class="v">{{ stats.missing }}</div>
      </div>
    </div>
  </div>
  <div v-else class="empty">import a dataset first</div>
</template>

<style scoped>
.explore { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; gap: 28px; flex-wrap: wrap; align-items: flex-end; }
.inline { display: flex; gap: 6px; }
.cards { display: flex; gap: 10px; flex-wrap: wrap; }
.stat { min-width: 92px; }
.stat .k { color: var(--muted); font-size: 11px; text-transform: capitalize; }
.stat .v { font-size: 16px; margin-top: 3px; }
.empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
