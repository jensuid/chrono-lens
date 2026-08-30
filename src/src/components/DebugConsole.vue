<script setup>
// Debug console: renders the request log from debug.js so GUI-only
// failures can be diagnosed without developer tools. Toggle with
// Cmd+Shift+D or the "diagnostics" link in the sidebar footer.
import { computed } from 'vue'
import { getLog } from '../debug.js'

const props = defineProps({ open: Boolean })

const entries = computed(() => (props.open ? getLog() : []))

async function runSelfTest() {
  // The selftest page is a static asset (public/selftest.html) shipped
  // in the bundle; it reads the port from the query string.
  try {
    const { invoke } = await import('@tauri-apps/api/core')
    const port = await invoke('backend_port')
    window.open(`selftest.html?port=${port}`, '_blank')
  } catch (e) {
    window.open('selftest.html', '_blank')
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="dbg-overlay" @click.self="$emit('close')">
      <div class="dbg">
        <header>
          <b>Diagnostics</b>
          <button @click="runSelfTest">network self-test</button>
          <button @click="$emit('close')">close</button>
        </header>
        <div class="entries">
          <div v-for="(e, i) in entries.slice().reverse()" :key="i" class="entry" :class="e.event">
            <span class="t">{{ e.at.split('T')[1].slice(0, 12) }}</span>
            <span class="k">{{ e.label }}</span>
            <span class="d">{{ e.detail }}</span>
          </div>
          <p v-if="!entries.length" class="empty">no requests traced — try an import</p>
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
}
header { display: flex; gap: 10px; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
header b { flex: 1; }
.entries { overflow-y: auto; padding: 10px 16px; font-family: ui-monospace, monospace; font-size: 12px; }
.entry { display: flex; gap: 10px; padding: 3px 0; }
.entry .t { color: var(--muted); }
.entry .k { color: var(--accent); min-width: 90px; }
.entry.error .d { color: var(--danger); }
.entry.response .d { color: var(--ok, #6c6); }
.empty { color: var(--muted); }
</style>
