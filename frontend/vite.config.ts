import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import dotenv from 'dotenv'
import path from 'path'

// Load env from current cwd and also from backend2/.env to reuse backend port
dotenv.config()
dotenv.config({ path: path.resolve(process.cwd(), '..', 'backend2', '.env') })

const BACKEND_HOST = process.env.BACKEND_HOST || 'localhost'
const BACKEND_PORT = process.env.BACKEND_PORT || process.env.PORT || '8080'
const API_URL = process.env.VITE_API_URL || `http://${BACKEND_HOST}:${BACKEND_PORT}`

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Allow reverse-proxied Host header from tracker.gonka.top
    allowedHosts: ['tracker.gonka.top'],
    proxy: {
      '/api': {
        target: API_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})

