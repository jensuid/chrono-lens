// Webview-side request debugger: captures every API call's method, URL,
// timing, and outcome into a reactive log the in-app debug console
// renders. Always active in the packaged app build so field reports
// include a trace.
import { ref } from 'vue'

const LOG_MAX = 200

// Reactive so the diagnostics console updates live while open — a plain
// array would never re-render mid-session (the network test's output
// would silently never appear).
const log = ref([])

function record(entry) {
  const stamped = { at: new Date().toISOString(), ...entry }
  log.value = [...log.value.slice(-(LOG_MAX - 1)), stamped]
  console.log('[chrono]', stamped.event, stamped.detail ?? '')
  return stamped
}

/** Append a custom entry (used by the in-console network self-test). */
export { record }

export function getLog() {
  return log.value
}

export async function tracedFetch(label, url, options = {}) {
  record({ event: 'request', label, detail: `${options.method ?? 'GET'} ${url}` })
  const t0 = performance.now()
  try {
    const response = await fetch(url, options)
    const body = await response.text()
    const ms = Math.round(performance.now() - t0)
    record({
      event: 'response',
      label,
      detail: `${response.status} ${response.statusText} (${ms} ms, ${body.length} bytes)`,
      status: response.status,
      bodyPreview: body.slice(0, 500),
    })
    let parsed = null
    try {
      parsed = JSON.parse(body)
    } catch {
      /* not JSON */
    }
    if (!response.ok) {
      const err = parsed?.error ?? {}
      const error = new Error(err.message ?? `request failed: ${response.status}`)
      error.code = err.code
      error.status = response.status
      throw error
    }
    return parsed
  } catch (e) {
    record({ event: 'error', label, detail: `${e.name}: ${e.message}` })
    throw e
  }
}

export async function tracedXhr(label, url, form) {
  record({ event: 'request', label, detail: `XHR POST ${url}` })
  const t0 = performance.now()
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.responseType = 'text'
    xhr.onload = () => {
      const ms = Math.round(performance.now() - t0)
      record({
        event: 'response',
        label,
        detail: `${xhr.status} (${ms} ms, ${xhr.response?.length ?? 0} bytes)`,
        status: xhr.status,
        bodyPreview: String(xhr.response ?? '').slice(0, 500),
      })
      let parsed = null
      try {
        parsed = JSON.parse(xhr.response)
      } catch {
        /* not JSON */
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(parsed)
      } else {
        const err = parsed?.error ?? {}
        const error = new Error(err.message ?? `request failed: ${xhr.status}`)
        error.code = err.code
        error.status = xhr.status
        reject(error)
      }
    }
    xhr.onerror = () => {
      record({
        event: 'error',
        label,
        detail: `XHR onerror readyState=${xhr.readyState} status=${xhr.status} (network-level failure: refused, CORS, or body rejected)`,
      })
      reject(new Error('Load failed'))
    }
    xhr.send(form)
  })
}
