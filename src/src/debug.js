// Webview-side request debugger: captures every API call's method, URL,
// timing, and outcome into a global log the in-app debug console renders.
// Enabled by launching the app with CHRONOLENS_DEBUG=1 or the
// ?debug URL param; always active in the packaged app build so field
// reports include a trace.

const log = []
const LOG_MAX = 200

function record(entry) {
  const stamped = { at: new Date().toISOString(), ...entry }
  log.push(stamped)
  if (log.length > LOG_MAX) log.shift()
  console.log('[chrono]', stamped.event, stamped.detail ?? '')
  return stamped
}

export function getLog() {
  return [...log]
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
