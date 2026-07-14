import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    include: ['@azure/msal-browser', '@azure/msal-react'],
  },
  server: {
    proxy: {
      '/auth': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/events': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/scans': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/users': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/admin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/system': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/reports': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/breaches': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api/webintel': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ctem': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/schedules': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ai-tools': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ai-scans': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/engagements': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
