import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// The app calls the API on its own origin, so the dev and preview servers
// forward /api and /ws to the backend. Point VITE_DEV_API_TARGET elsewhere if
// the backend does not run on port 8000.
const target = process.env.VITE_DEV_API_TARGET || 'http://localhost:8000'

const proxy = {
  '/api': { target, changeOrigin: true },
  '/ws': { target, ws: true, changeOrigin: true },
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy },
  preview: { proxy },
})
