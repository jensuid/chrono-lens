<script setup>
// Decompose view: STL/classical panels, ADF/KPSS, ACF/PACF.
import { computed, reactive, ref, watch } from 'vue'
import { postJson } from '../api.js'
import TimeChart from '../components/TimeChart.vue'
import { COLORS, AXIS_STYLE, lineChartOption, lineSeries } from '../components/chartOptions.js'

const props = defineProps({ dataset: { type: Object, default: null } })

const column = ref('')
const error = ref('')
const loading = ref(false)
const deco = ref(null)
const stationarity = ref(null)
const acfData = ref(null)

const params = reactive({ period: 7, method: 'stl', nlags: 30 })

function plainOption(points, color, yName = '') {
  return lineChartOption([lineSeries('series', points, { lineStyle: { color } })], { yName })
}

const observedOption = computed(() => plainOption(deco.value?.observed, COLORS[0]))
const trendOption = computed(() => plainOption(deco.value?.trend, COLORS[1]))
const seasonalOption = computed(() => plainOption(deco.value?.seasonal, COLORS[2]))
const residualOption = computed(() => plainOption(deco.value?.residual, COLORS[3]))

const acfOption = computed(() => {
  if (!acfData.value) return {}
  const band = acfData.value.band
  const lags = acfData.value.acf.map((_, i) => i)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 24, bottom: 36 },
    xAxis: { type: 'category', data: lags, name: 'lag', ...AXIS_STYLE },
    yAxis: { type: 'value', ...AXIS_STYLE },
    series: [
      {
        type: 'bar',
        data: acfData.value.acf,
        itemStyle: { color: COLORS[1] },
      },
      {
        type: 'line',
        data: lags.map(() => band),
        lineStyle: { type: 'dashed', color: '#94a3b8' },
        symbol: 'none',
      },
      {
        type: 'line',
        data: lags.map(() => -band),
        lineStyle: { type: 'dashed', color: '#94a3b8' },
        symbol: 'none',
      },
    ],
  }
})

const pacfOption = computed(() => {
  if (!acfData.value) return {}
  const band = acfData.value.band
  const lags = acfData.value.pacf.map((_, i) => i)
  return {
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 24, bottom: 36 },
    xAxis: { type: 'category', data: lags, name: 'lag', ...AXIS_STYLE },
    yAxis: { type: 'value', ...AXIS_STYLE },
    series: [
      { type: 'bar', data: acfData.value.pacf, itemStyle: { color: COLORS[2] } },
      { type: 'line', data: lags.map(() => band), lineStyle: { type: 'dashed', color: '#94a3b8' }, symbol: 'none' },
      { type: 'line', data: lags.map(() => -band), lineStyle: { type: 'dashed', color: '#94a3b8' }, symbol: 'none' },
    ],
  }
})

watch(
  () => props.dataset?.id,
  () => {
    deco.value = null
    stationarity.value = null
    acfData.value = null
    column.value = props.dataset?.numericColumns[0] ?? ''
  },
  { immediate: true },
)

async function runAll() {
  if (!props.dataset || !column.value) return
  error.value = ''
  loading.value = true
  const id = props.dataset.id
  try {
    deco.value = await postJson(`/api/datasets/${id}/decompose`, {
      column: column.value,
      period: params.period,
      method: params.method,
    })
    stationarity.value = await postJson(`/api/datasets/${id}/stationarity`, {
      column: column.value,
    })
    acfData.value = await postJson(`/api/datasets/${id}/acf`, {
      column: column.value,
      nlags: params.nlags,
    })
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="decompose" v-if="dataset">
    <div class="toolbar">
      <div>
        <label>value column</label>
        <select v-model="column">
          <option v-for="c in dataset.numericColumns" :key="c" :value="c">{{ c }}</option>
        </select>
      </div>
      <div>
        <label>period</label>
        <input v-model.number="params.period" type="number" min="2" style="width: 90px" />
      </div>
      <div>
        <label>method</label>
        <select v-model="params.method">
          <option value="stl">STL</option>
          <option value="classical">classical</option>
        </select>
      </div>
      <div>
        <label>ACF lags</label>
        <input v-model.number="params.nlags" type="number" min="1" max="500" style="width: 90px" />
      </div>
      <div style="align-self: flex-end">
        <button class="primary" :disabled="loading" @click="runAll">
          <span v-if="loading" class="spinner"></span> run
        </button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <template v-if="deco">
      <div class="quad">
        <div class="card"><label>observed</label><TimeChart :option="observedOption" height="190px" /></div>
        <div class="card"><label>trend</label><TimeChart :option="trendOption" height="190px" /></div>
        <div class="card"><label>seasonal</label><TimeChart :option="seasonalOption" height="190px" /></div>
        <div class="card"><label>residual</label><TimeChart :option="residualOption" height="190px" /></div>
      </div>
    </template>

    <div class="tests" v-if="stationarity">
      <div class="card test">
        <h3>ADF test <span :class="stationarity.adf.pvalue < 0.05 ? 'ok' : 'bad'">{{ stationarity.adf.pvalue < 0.05 ? 'stationary' : 'non-stationary' }}</span></h3>
        <div class="row"><span>statistic</span><b>{{ stationarity.adf.statistic.toFixed(4) }}</b></div>
        <div class="row"><span>p-value</span><b>{{ stationarity.adf.pvalue.toFixed(4) }}</b></div>
        <p>{{ stationarity.adf.interpretation }}</p>
      </div>
      <div class="card test">
        <h3>KPSS test <span :class="stationarity.kpss.pvalue < 0.05 ? 'bad' : 'ok'">{{ stationarity.kpss.pvalue < 0.05 ? 'non-stationary' : 'stationary' }}</span></h3>
        <div class="row"><span>statistic</span><b>{{ stationarity.kpss.statistic.toFixed(4) }}</b></div>
        <div class="row"><span>p-value</span><b>{{ stationarity.kpss.pvalue.toFixed(4) }}</b></div>
        <p>{{ stationarity.kpss.interpretation }}</p>
      </div>
    </div>

    <div class="acf" v-if="acfData">
      <div class="card"><label>ACF</label><TimeChart :option="acfOption" height="220px" /></div>
      <div class="card"><label>PACF</label><TimeChart :option="pacfOption" height="220px" /></div>
    </div>
  </div>
  <div v-else class="empty">import a dataset first</div>
</template>

<style scoped>
.decompose { display: flex; flex-direction: column; gap: 14px; }
.toolbar { display: flex; gap: 22px; flex-wrap: wrap; align-items: flex-end; }
.quad { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.tests { display: flex; gap: 12px; flex-wrap: wrap; }
.test { flex: 1; min-width: 260px; }
.test h3 { margin: 0 0 8px; font-size: 14px; display: flex; justify-content: space-between; align-items: center; }
.test .row { display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; }
.test p { color: var(--muted); font-size: 12px; margin: 8px 0 0; }
.ok { color: var(--ok); }
.bad { color: var(--danger); }
.acf { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.empty { color: var(--muted); padding: 40px; text-align: center; }
</style>
