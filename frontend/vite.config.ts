/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

import { developmentHeaders, productionHeaders } from './security-headers'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    headers: developmentHeaders,
    // The backend is reached through /api, so the browser sees one origin:
    // no CORS, and the SameSite=Strict session cookies are sent normally.
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    // Vite inlines files under 4 kB as data: URIs, small font subsets
    // included. Fonts stay files, so the policy's font-src 'self' covers them.
    assetsInlineLimit: (file) => (/\.woff2?$/.test(file) ? false : undefined),
  },
  // `vite preview` serves the production build, with the production policy.
  // It proxies /api like the dev server.
  preview: {
    headers: productionHeaders,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
