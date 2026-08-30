// Shared chart option builders for ChronoLens views.

const AXIS_TIME = {
  type: 'time',
  axisLabel: { formatter: (v) => new Date(v).toLocaleDateString() },
}

const GRID = { left: 60, right: 24, top: 30, bottom: 56 }

const DATA_ZOOM = [
  { type: 'inside' },
  { type: 'slider', height: 18, bottom: 12 },
]

const TOOLTIP_TIME = {
  trigger: 'axis',
  formatter: (params) => {
    const date = new Date(params[0]?.value?.[0] ?? params[0]?.axisValue).toLocaleString()
    const lines = [date]
    for (const p of params) {
      if (p.value == null || p.value[1] == null) continue
      lines.push(`${p.marker} ${p.seriesName}: ${Number(p.value[1]).toFixed(2)}`)
    }
    return lines.join('<br>')
  },
}

/** Base dark theme colors. */
export const COLORS = [
  '#40e0d0', '#ffbf40', '#7aa2ff', '#ff5d73', '#4ade80', '#c792ea',
]

/** One line series from [{t, v}] points (nulls become gaps). */
export function lineSeries(name, points, extra = {}) {
  return {
    name,
    type: 'line',
    showSymbol: false,
    connectNulls: false,
    data: (points ?? []).map((p) => [p.t, p.v]),
    ...extra,
  }
}

/** A scatter series (anomaly markers). */
export function scatterSeries(name, points, extra = {}) {
  return {
    name,
    type: 'scatter',
    data: (points ?? []).map((p) => [p.t, p.v]),
    symbolSize: 9,
    ...extra,
  }
}

/** A confidence-interval band rendered as a stacked area. */
export function bandSeries(name, lowPoints, highPoints, color = '#7aa2ff') {
  const base = highPoints.map((p) => [p.t, p.v])
  const diff = highPoints.map((p, i) => [p.t, p.v - (lowPoints[i]?.v ?? p.v)])
  return [
    { name: `${name} band`, type: 'line', data: base, lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', silent: true },
    { name: `${name} band`, type: 'line', data: diff, lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', silent: true, areaStyle: { color, opacity: 0.18 }, tooltip: { show: false } },
  ]
}

/** Standard line chart option with zoom. */
export function lineChartOption(series, { yName = '', zoom = true, height } = {}) {
  return {
    color: COLORS,
    tooltip: TOOLTIP_TIME,
    grid: GRID,
    xAxis: AXIS_TIME,
    yAxis: { type: 'value', name: yName, scale: true },
    dataZoom: zoom ? DATA_ZOOM : [],
    series,
  }
}
