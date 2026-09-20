import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The app always calls a relative /api path. In production FastAPI serves
  // this bundle and the API from one origin; in development this proxy stands
  // in for that, so the client code is identical in both. 127.0.0.1 rather
  // than localhost: on a dual-stack Mac localhost can resolve to ::1 while
  // uvicorn is listening on IPv4 only.
  // VITE_API_TARGET lets a second worktree point its dev server at its own
  // backend port. Without it every worktree's frontend proxies to 8000, which
  // is whichever backend happened to start first.
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
