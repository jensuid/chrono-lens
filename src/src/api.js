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

async function uploadFile(file, sheet = null) {
  const form = new FormData()
  form.append('file', file, file.name)
  if (sheet) form.append('sheet', sheet)
  return request('/api/datasets', { method: 'POST', body: form })
}

async function deleteDataset(id) {
  return request(`/api/datasets/${id}`, { method: 'DELETE' })
}

export { getJson, postJson, uploadFile, deleteDataset }
