// API client: port-aware for the packaged app, dev-proxy fallback.
//
// In the Tauri app the Python sidecar listens on a port chosen at launch;
// the Rust shell exposes it through the `backend_port` command. Under
// `npm run dev` (browser) requests go through the Vite proxy instead.
// All requests are traced through debug.js for the in-app console.

import { tracedFetch, tracedXhr } from './debug.js'

let cachedPort = null
let portPromise = null

async function backendPort() {
  if (cachedPort) return cachedPort
  if (!portPromise) {
    portPromise = (async () => {
      try {
        const { invoke } = await import('@tauri-apps/api/core')
        cachedPort = await invoke('backend_port')
      } catch {
        // Not running inside Tauri (browser dev mode): use the relative path
        // served by the Vite proxy.
        cachedPort = null
      }
      return cachedPort
    })()
  }
  return portPromise
}

async function base() {
  const port = await backendPort()
  return port ? `http://127.0.0.1:${port}` : ''
}

async function request(path, options = {}, label = path) {
  const url = `${await base()}${path}`
  return tracedFetch(label, url, options)
}

async function getJson(path) {
  return request(path, {}, `GET ${path}`)
}

async function postJson(path, payload) {
  return request(
    path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
    `POST ${path}`,
  )
}

async function uploadFile(file, sheet = null) {
  const form = new FormData()
  form.append('file', file, file.name)
  if (sheet) form.append('sheet', sheet)
  const url = `${await base()}/api/datasets`
  return tracedXhr(`UPLOAD ${file.name}`, url, form)
}

async function deleteDataset(id) {
  return request(`/api/datasets/${id}`, { method: 'DELETE' })
}

export { getJson, postJson, uploadFile, deleteDataset }
