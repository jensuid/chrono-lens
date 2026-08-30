<script setup>
// Forecast view: SARIMA / Holt-Winters tabs, horizon + train-ratio, metrics.
import { computed, reactive, ref, watch } from 'vue'
import { postJson } from '../api.js'
import TimeChart from '../components/TimeChart.vue'
import { COLORS, lineChartOption, lineSeries, bandSeries } from '../components/chartOptions.js'

const props = defineProps({ dataset: { type: Object, default: null } })

const column = ref('')
const model = ref('sarima')
const error = ref('')
const loading = ref(false)
const result = ref(null)

const params = reactive({
  horizon: 30,
  trainRatio: 0.8,
  // SARIMA
  order: [1, 1, 1],
  seasonalOrder: [1, 0, 1, 7],
  // Holt-Winters
  trend: 'add',
  seasonal: 'add',
  seasonalPeriods: 7,
})

const chartOption = computed(() => {
  if (!result.value) return {}
  const r = result.value
  const series = [
    lineSeries('train', r.train, { lineStyle: { color: COLORS[0], opacity: 0.7 } }),
    lineSeries('actual (test)', r.test, { lineStyle: { color: COLORS[4], type: 'dashed' } }),
    lineSeries('fitted', r.fitted, { lineStyle: { color: COLORS[1] } }),
    lineSeries('forecast', r.forecast.points, { lineStyle: { color: COLORS[3], width: 2 } }),
  ]
  if (r.forecast.low?.length) series.push(...bandSeries('forecast', r.forecast.low, r.forecast.high, COLORS[3]))
  return lineChartOption(series)
})

watch(
  () => props.dataset?.id,
  () => {
    result.value = null
    column.value = props.dataset?.numericColumns[0] ?? ''
  },
  { immediate: true },
)

async function run() {
  if (!props.dataset || !column.value) return
  error.value = ''
  loading.value = true
  const id = props.dataset.id
  try {
    if (model.value === 'sarima') {
      result.value = await postJson(`/api/datasets/${id}/forecast/sarima`, {
        column: column.value,
        horizon: params.horizon,
        trainRatio: params.trainRatio,
        order: params.order,
        seasonalOrder: params.seasonalOrder,
      })
    } else {
      result.value = await postJson(`/api/datasets/${id}/forecast/hw`, {
        column: column.value,
        horizon: params.horizon,
        trainRatio: params.trainRatio,
        trend: params.trend,
        seasonal: params.seasonal,
        seasonalPeriods: params.seasonal === 'None' ? null : params.seasonalPeriods,
      })
    }
  } catch (e) {
    error.value = e.message
    result.value = null
  } finally {
    loading.value = false
  }
}

function fmt(n) {
  return n == null ? '—' : n.toLocaleString(undefined, { maximumFractionDigits: 3 })
}
</script>

<template>
  <div class="forecast" v-if="dataset">
    <div class="toolbar">
      <div>
        <label>model</label>
        <select v-model="model">
          <option value="sarima">SARIMA</option>
          <option value="hw">Holt-Winters</option>
        </select>
      </div>
      <div>
        <label>value column</label>
        <select v-model="column">
          <option v-for="c in dataset.numericColumns" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label>horizon: {{ params.horizon }}</label>
        <input v-model.number="params.horizon" type="range" min="1" max="90" />
      </div>
      <div>
        <label>train ratio: {{ (params.trainRatio * 100).toFixed(0) }}%</label>
        <input v-model.number="params.trainRatio" type="range" min="0.55" max="0.95" step="0.05" />
      </div>

      <template v-if="model === 'sarima'">
        <div>
          <label>order (p,d,q)</label>
          <div class="inline">
            <input v-model.number="params.order[0]" type="number" min="0" max="5" style="width: 54px" />
            <input v-model.number="params.order[1]" type="number" min="0" max="2" style="width: 54px" />
            <input v-model.number="params.order[2]" type="number" min="0" max="5" style="width: 54px" />
          </div>
        </div>
        <div>
          <label>seasonal (P,D,Q,s)</label>
          <div class="inline">
            <input v-model.number="params.seasonalOrder[0]" type="number" min="0" max="3" style="width: 46px" />
            <input v-model.number="params.seasonalOrder[1]" type="number" min="0" max="1" style="width: 46px" />
            <input v-model.number="params.seasonalOrder[2]" type="number" min="0" max="3" style="width: 46px" />
            <input v-model.number="params.seasonalOrder[3]" type="number" min="2" max="52" style="width: 60px" />
          </div>
        </div>
      </template>

      <template v-else>
        <div>
          <label>trend</label>
          <select v-model="params.trend">
            <option value="add">additive</option>
            <option value="mul">multiplicative</option>
            <option value="None">none</option>
          </select>
        </div>
        <div>
          <label>seasonal</label>
          <select v-model="params.seasonal">
            <option value="add">additive</option>
            <option value="mul">multiplicative</option>
            <option value="None">none</option>
          </select>
        </div>
        <div v-if="params.seasonal !== 'None'">
          <label>seasonal periods</label>
          <input v-model.number="params.seasonalPeriods" type="number" min="2" style="width: 80px" />
        </div>
      </template>

      <div style="align-self: flex-end">
        <button class="primary" :disabled="loading" @click="run">
          <span v-if="loading" class="spinner"></span> forecast
        </button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <TimeChart v-if="result" :option="chartOption" height="430px" />

    <div class="cards" v-if="result">
      <div class="card stat"><div class="k">MAE</div><div class="v">{{ fmt(result.metrics.mae) }}</div></div>
      <div class="card stat"><div class="k">RMSE</div><div class="v">{{ fmt(result.metrics.rmse) }}</div></div>
      <div class="card stat"><div class="k">MAPE</div><div class="v">{{ result.metrics.mape == null ? '—' : result.metrics.mape.toFixed(2) + '%' }}</div></div>
    </div>
  </div>
  <div v-else class="empty">import a dataset first</div>
</template>

<style scoped>
.forecast { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; gap: 20px; flex-wrap: wrap; align-items: flex-end; }
.inline { display: flex; gap: 6px; }
.cards { display: flex; gap: 10px; }
.stat { min-width: 110px; }
.stat .k { color: var(--muted); font-size: 11px; text-transform: uppercase; }
.stat .v { font-size: 16px; margin-top: 3px; }
.empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
