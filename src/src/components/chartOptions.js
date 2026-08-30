// Shared chart option builders for ChronoLens views.
// Light theme: ink text on white cards, saturated-but-soft series colors
// that stay distinguishable on #ffffff.

const AXIS_TIME = {
  type: 'time',
  axisLabel: { formatter: (v) => new Date(v).toLocaleDateString() },
}

const GRID = { left: 60, right: 24, top: 30, bottom: 56 }

const DATA_ZOOM = [
  { type: 'inside' },
  { type: 'slider', height: 18, bottom: 12, borderColor: '#dce4ee', fillerColor: 'rgba(13, 148, 136, 0.12)' },
]

const TOOLTIP_TIME = {
  trigger: 'axis',
  backgroundColor: '#ffffff',
  borderColor: '#dce4ee',
  textStyle: { color: '#1c2b3a' },
  extraCssText: 'box-shadow: 0 4px 14px rgba(28,43,58,0.12); border-radius: 8px;',
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

/** Light-theme series palette (teal lead, amber, indigo, rose, green, violet). */
export const COLORS = [
  '#0d9488', '#d97706', '#4f46e5', '#e11d48', '#16a34a', '#9333ea',
]

/** Shared axis styling for the light theme. */
export const AXIS_STYLE = {
  axisLabel: { color: '#64748b' },
  axisLine: { lineStyle: { color: '#dce4ee' } },
  splitLine: { lineStyle: { color: '#eef2f7' } },
  nameTextStyle: { color: '#64748b' },
}

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
export function bandSeries(name, lowPoints, highPoints, color = '#4f46e5') {
  const base = highPoints.map((p) => [p.t, p.v])
  const diff = highPoints.map((p, i) => [p.t, p.v - (lowPoints[i]?.v ?? p.v)])
  return [
    { name: `${name} band`, type: 'line', data: base, lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', silent: true },
    { name: `${name} band`, type: 'line', data: diff, lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', silent: true, areaStyle: { color, opacity: 0.15 }, tooltip: { show: false } },
  ]
}

/** Standard line chart option with zoom. */
export function lineChartOption(series, { yName = '', zoom = true, height } = {}) {
  return {
    color: COLORS,
    tooltip: TOOLTIP_TIME,
    grid: GRID,
    xAxis: { ...AXIS_TIME, ...AXIS_STYLE },
    yAxis: { type: 'value', name: yName, scale: true, ...AXIS_STYLE },
    dataZoom: zoom ? DATA_ZOOM : [],
    series,
  }
}
