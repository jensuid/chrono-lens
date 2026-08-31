<script setup>
// Debug console: renders the request log from debug.js so GUI-only
// failures can be diagnosed without developer tools, plus an inline
// network self-test. Toggle with Cmd+Shift+D or the sidebar footer link.
//
// The self-test runs in-app (no window.open: WKWebView in Tauri has no
// new-window handling — a silent no-op). It exercises exactly the
// transports the app uses: fetch GET, XHR multipart upload, fetch
// multipart upload, and deletes the datasets it creates.
import { computed, ref } from 'vue'
import { getLog, record } from '../debug.js'
import { baseUrl, deleteDataset } from '../api.js'

const props = defineProps({ open: Boolean })

const entries = computed(() => (props.open ? getLog() : []))
const testing = ref(false)

const TEST_CSV = 'timestamp,value\n2023-01-01,1\n2023-01-02,2\n2023-01-03,3\n2023-01-04,4\n'

async function probeGet(base) {
  try {
    const r = await fetch(`${base}/api/health`)
    const t = await r.text()
    record({
      event: r.ok ? 'response' : 'error',
      label: 'test GET',
      detail: `fetch GET /api/health -> ${r.status} ${t.slice(0, 40)}`,
    })
    return r.ok
  } catch (e) {
    record({ event: 'error', label: 'test GET', detail: `fetch GET -> ${e.name}: ${e.message}` })
    return false
  }
}

async function probeFetch(base, form) {
  try {
    const r = await fetch(`${base}/api/datasets`, { method: 'POST', body: form })
    const t = await r.text()
    record({
      event: r.ok ? 'response' : 'error',
      label: 'test fetch',
      detail: `fetch upload -> ${r.status}: ${t.slice(0, 80)}`,
    })
    return r.ok
  } catch (e) {
    record({
      event: 'error',
      label: 'test fetch',
      detail: `fetch upload -> ${e.name}: ${e.message}` +
        (String(e.message).includes('Load failed') ? '  <- the known WKWebView bug' : ''),
    })
    return false
  }
}

function xhrResultId(xhr) {
  try {
    return JSON.parse(xhr.response)?.id ?? null
  } catch {
    return null
  }
}

async function runSelfTest() {
  if (testing.value) return
  testing.value = true
  const base = await baseUrl()
  const created = []
  try {
    await probeGet(base)

    // XHR multipart upload — the transport real imports use.
    const xform = new FormData()
    xform.append('file', new File([TEST_CSV], 'selftest-xhr.csv', { type: 'text/csv' }))
    const xid = await new Promise((resolve) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${base}/api/datasets`)
      xhr.onload = () => {
        const ok = xhr.status >= 200 && xhr.status < 300
        record({
          event: ok ? 'response' : 'error',
          label: 'test XHR',
          detail: `XHR upload -> ${xhr.status}: ${String(xhr.response).slice(0, 80)}`,
        })
        resolve(ok ? xhrResultId(xhr) : null)
      }
      xhr.onerror = () => {
        record({
          event: 'error',
          label: 'test XHR',
          detail: 'XHR upload -> onerror (network-level: refused / CORS / body rejected)',
        })
        resolve(null)
      }
      xhr.send(xform)
    })
    if (xid) created.push(xid)

    // fetch multipart upload — the path WKWebView historically rejects.
    const fform = new FormData()
    fform.append('file', new File([TEST_CSV], 'selftest-fetch.csv', { type: 'text/csv' }))
    const fOk = await probeFetch(base, fform)
    if (fOk) {
      // Re-list to find the created id (the response body has it).
      try {
        const list = await (await fetch(`${base}/api/datasets`)).json()
        const mine = list.find((d) => d.name === 'selftest-fetch.csv')
        if (mine) created.push(mine.id)
      } catch { /* best effort */ }
    }

    // Clean up everything this test created.
    for (const id of created) {
      try {
        await deleteDataset(id)
      } catch { /* best effort */ }
    }
    if (created.length) {
      record({ event: 'response', label: 'test cleanup', detail: `removed ${created.length} test dataset(s)` })
    }
    record({ event: 'response', label: 'test done', detail: 'network self-test finished' })
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dbg-overlay" @click.self="$emit('close')">
      <div class="dbg">
        <header>
          <b>Diagnostics</b>
          <button class="primary" :disabled="testing" @click="runSelfTest">
            <span v-if="testing" class="spinner"></span>
            {{ testing ? 'testing…' : 'network test' }}
          </button>
          <button @click="$emit('close')">close</button>
        </header>
        <div class="entries">
          <div v-for="(e, i) in entries.slice().reverse()" :key="i" class="entry" :class="e.event">
            <span class="t">{{ e.at.split('T')[1].slice(0, 12) }}</span>
            <span class="k">{{ e.label }}</span>
            <span class="d">{{ e.detail }}</span>
          </div>
          <p v-if="!entries.length" class="empty">no requests traced — try an import, or run the network test</p>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dbg-overlay {
  position: fixed; inset: 0; background: rgba(28, 43, 58, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.dbg {
  background: var(--panel); border: 1px solid var(--border); border-radius: 12px;
  width: min(860px, 92vw); max-height: 80vh; display: flex; flex-direction: column;
  box-shadow: 0 12px 40px rgba(28, 43, 58, 0.25);
}
header { display: flex; gap: 10px; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
header b { flex: 1; }
header button.primary { font-size: 12px; padding: 5px 12px; }
.entries { overflow-y: auto; padding: 10px 16px; font-family: ui-monospace, monospace; font-size: 12px; }
.entry { display: flex; gap: 10px; padding: 3px 0; }
.entry .t { color: var(--muted); }
.entry .k { color: var(--accent); min-width: 90px; }
.entry.error .d { color: var(--danger); }
.entry.response .d { color: var(--ok, #6c6); }
.empty { color: var(--muted); }
</style>
