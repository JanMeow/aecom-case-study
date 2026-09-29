import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// /api/* is forwarded to the FastAPI backend, so the browser never needs CORS
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // MapLibre loads its worker (maplibre-gl-worker.mjs) from next to itself; pre-bundling moves the library
  // into .vite/deps without the worker, so the map never gets data. Serve it from node_modules as is.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  // MapLibre starts its worker as a module worker ({ type: 'module' }), so bundle workers as ES modules
  worker: { format: 'es' },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', rewrite: (path) => path.replace(/^\/api/, '') },
    },
  },
})
