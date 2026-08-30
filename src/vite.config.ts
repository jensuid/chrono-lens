import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// The dev server proxies /api to the local uvicorn instance; in the
// packaged app the frontend learns the sidecar port from Tauri instead.
export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8756',
        changeOrigin: true,
      },
    },
  },
  build: {
    target: 'es2022',
    outDir: 'dist',
  },
})
