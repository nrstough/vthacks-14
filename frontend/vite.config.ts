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
  // Recharts and what it pulls in (d3, Redux Toolkit, immer, es-toolkit, …) is
  // more than half the bundle, is imported only by BalanceChart, and changes far
  // less often than the app. Its own chunk keeps both under the 500 kB warning
  // and lets an app-only redeploy leave it cached. It is still a static import,
  // preloaded from index.html, not lazy-loaded: the chart is on the first screen.
  // Rolldown also moves the small React modules the chart shares with the app
  // into this chunk (includeDependenciesRecursively, on by default), so the two
  // chunks never import each other in a cycle.
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'charts',
              test: /node_modules[\\/](recharts|victory-vendor|d3-[^\\/]+|internmap|@reduxjs[\\/]toolkit|redux|redux-thunk|react-redux|reselect|immer|es-toolkit|decimal\.js-light|eventemitter3|use-sync-external-store|clsx)[\\/]/,
            },
          ],
        },
      },
    },
  },
})
