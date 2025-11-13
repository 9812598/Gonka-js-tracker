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

// Optional HMR configuration for running dev server behind a public HTTPS domain
const HMR_HOST = process.env.HMR_HOST || undefined
const HMR_PROTOCOL = process.env.HMR_PROTOCOL || undefined // e.g. 'wss' when behind HTTPS
const HMR_CLIENT_PORT = process.env.HMR_CLIENT_PORT ? parseInt(process.env.HMR_CLIENT_PORT, 10) : undefined

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Allow reverse-proxied Host header from tracker.gonka.top
    allowedHosts: ['tracker.gonka.top'],
    hmr: {
      host: HMR_HOST,
      protocol: HMR_PROTOCOL,
      clientPort: HMR_CLIENT_PORT
    },
    proxy: {
      '/api': {
        target: API_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
  }
})

