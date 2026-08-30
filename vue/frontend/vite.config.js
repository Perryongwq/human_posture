import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import basicSsl from '@vitejs/plugin-basic-ssl'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => ({
  plugins: [
    vue({
      template: { transformAssetUrls: false },
    }),
    ...(mode !== 'test' ? [tailwindcss()] : []),
    // HTTPS in dev — getUserMedia (webcam) requires a secure context when
    // the app is opened from another PC. Self-signed: accept the browser warning.
    ...(mode === 'development' ? [basicSsl()] : []),
  ],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

  server: {
    host: true,        // listen on LAN, not just localhost
    port: 5175,        // 5173/5174 already in use on this machine
    proxy: {
      // same-origin /api → local FastAPI; avoids CORS + mixed-content entirely.
      // 127.0.0.1, not localhost: Docker/WSL listen on ::1:8010 here, so
      // "localhost" can resolve to them instead of uvicorn.
      '/api': 'http://127.0.0.1:8011',
      // /ollama → local Ollama, so another PC can reach it via the already
      // LAN-open :5175 — no firewall rule, Ollama stays bound to 127.0.0.1.
      '/ollama': {
        target: 'http://127.0.0.1:11434',
        changeOrigin: true,
        rewrite: p => p.replace(/^\/ollama/, ''),
      },
    },
  },

  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.js'],
    testTimeout: 15000,
    poolOptions: {
      forks: { singleFork: true },
    },
  },
}))
