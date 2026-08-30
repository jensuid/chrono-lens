<script setup>
// Import view: file drop / picker, sheet selection, preview.
import { computed, ref } from 'vue'
import { uploadFile, getJson } from '../api.js'

const emit = defineEmits(['imported'])
const props = defineProps({
  dataset: { type: Object, default: null },
  backendReady: { type: Boolean, default: true },
})

const file = ref(null)
const sheet = ref('')
const sheets = ref(null)
const uploading = ref(false)
const error = ref('')
const preview = ref(null)

const canImport = computed(() => !!file.value && props.backendReady)

function onDrop(event) {
  const files = event.dataTransfer?.files
  if (files?.length) pickFile(files[0])
}

function onFileInput(event) {
  const f = event.target.files?.[0]
  if (f) pickFile(f)
  // Allow picking the same file again to retry after an error.
  event.target.value = ''
}

function pickFile(f) {
  error.value = ''
  preview.value = null
  sheets.value = null
  sheet.value = ''
  file.value = f
}

async function doImport() {
  if (!file.value) return
  uploading.value = true
  error.value = ''
  try {
    const meta = await uploadFile(file.value, sheet.value || null)
    emit('imported', meta)
  } catch (e) {
    error.value = e.message
  } finally {
    uploading.value = false
  }
}

async function loadPreview(meta) {
  try {
    preview.value = await getJson(`/api/datasets/${meta.id}/preview?limit=50`)
  } catch {
    /* preview is best-effort */
  }
}
</script>

<template>
  <div class="import">
    <h2>Import a time series</h2>
    <p class="hint">
      Drop a <b>.csv</b>, <b>.json</b> (array of records), <b>.xlsx</b>, or <b>.xls</b> file.
      ChronoLens auto-detects the datetime and numeric columns.
      Sample files ship in the <code>sample_data/</code> folder.
    </p>

    <div
      class="dropzone"
      :class="{ has: file }"
      @dragover.prevent
      @drop.prevent="onDrop"
      @click="$refs.fileInput.click()"
    >
      <input ref="fileInput" type="file" accept=".csv,.json,.xlsx,.xls" hidden @change="onFileInput" />
      <template v-if="file">
        <div class="fname">{{ file.name }}</div>
        <div class="fsize">{{ (file.size / 1024).toFixed(1) }} KiB</div>
      </template>
      <template v-else>
        <div class="dz-big">⬇︎</div>
        <div>drop a file here, or click to browse</div>
      </template>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="row" v-if="file">
      <button class="primary" :disabled="!canImport || uploading" @click="doImport">
        <span v-if="uploading" class="spinner"></span>
        {{ backendReady ? 'Import' : 'Import (waiting for backend…)' }}
      </button>
    </div>

    <div v-if="dataset" class="card meta">
      <h3>Current dataset</h3>
      <div class="facts">
        <div><b>{{ dataset.rows }}</b> rows</div>
        <div>datetime column: <b>{{ dataset.datetimeColumn }}</b></div>
        <div>numeric: <b>{{ dataset.numericColumns.join(', ') }}</b></div>
        <div v-if="dataset.warnings?.length" class="warn">{{ dataset.warnings.join(' · ') }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.import { max-width: 720px; display: flex; flex-direction: column; gap: 16px; }
h2 { margin: 0 0 -6px; }
.hint { color: var(--muted); font-size: 13px; margin: 0; }
.dropzone {
  border: 2px dashed var(--border);
  border-radius: 12px;
  padding: 46px 20px;
  text-align: center;
  color: var(--muted);
  cursor: pointer;
  transition: border-color 0.15s;
}
.dropzone:hover, .dropzone.has { border-color: var(--accent); color: var(--text); }
.dz-big { font-size: 34px; margin-bottom: 6px; }
.fname { font-size: 15px; color: var(--accent); word-break: break-all; }
.fsize { font-size: 12px; color: var(--muted); margin-top: 4px; }
.row { display: flex; gap: 10px; }
.meta h3 { margin: 0 0 8px; font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; }
.facts { display: flex; flex-direction: column; gap: 4px; font-size: 13px; }
.warn { color: var(--accent-2); font-size: 12px; margin-top: 6px; }
</style>
