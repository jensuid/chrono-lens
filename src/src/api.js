// API client: port-aware for the packaged app, dev-proxy fallback.
//
// In the Tauri app the Python sidecar listens on a port chosen at launch;
// the Rust shell exposes it through the `backend_port` command. Under
// `npm run dev` (browser) requests go through the Vite proxy instead.

let cachedPort = null

async function backendPort() {
  if (cachedPort) return cachedPort
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    cachedPort = await invoke('backend_port')
  } catch {
    // Not running inside Tauri (browser dev mode): use the relative path
    // served by the Vite proxy.
    cachedPort = null
  }
  return cachedPort
}

async function base() {
  const port = await backendPort()
  return port ? `http://127.0.0.1:${port}` : ''
}

async function request(path, options = {}) {
  const url = `${await base()}${path}`
  const response = await fetch(url, options)
  let body = null
  try {
    body = await response.json()
  } catch {
    body = null
  }
  if (!response.ok) {
    const err = body?.error ?? {}
    const error = new Error(err.message ?? `request failed: ${response.status}`)
    error.code = err.code
    error.status = response.status
    throw error
  }
  return body
}

async function getJson(path) {
  return request(path)
}

async function postJson(path, payload) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

function uploadFileViaXhr(url, form) {
  // WKWebView (the packaged app's webview) fails fetch() with "Load
  // failed" when the body is a FormData containing a File — a known
  // WebKit bug. XHR handles multipart uploads fine, so uploads use it
  // unconditionally; it behaves identically in the browser.
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', url)
    xhr.responseType = 'json'
    xhr.onload = () => {
      const body = xhr.response
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body)
      } else {
        const err = body?.error ?? {}
        const error = new Error(err.message ?? `request failed: ${xhr.status}`)
        error.code = err.code
        error.status = xhr.status
        reject(error)
      }
    }
    xhr.onerror = () => reject(new Error('Load failed'))
    xhr.send(form)
  })
}

async function uploadFile(file, sheet = null) {
  const form = new FormData()
  form.append('file', file, file.name)
  if (sheet) form.append('sheet', sheet)
  const url = `${await base()}/api/datasets`
  return uploadFileViaXhr(url, form)
}

async function deleteDataset(id) {
  return request(`/api/datasets/${id}`, { method: 'DELETE' })
}

export { getJson, postJson, uploadFile, deleteDataset }
