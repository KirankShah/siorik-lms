/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Several enterprise learners are on Windows 7/8.1 devices whose last
    // available Chromium release is 109. Keep the production bundle within
    // that syntax/CSS baseline; the static compatibility notice in index.html
    // handles anything older before React needs to start.
    target: ['chrome109', 'edge109', 'firefox114', 'safari16.4'],
    cssTarget: ['chrome109', 'edge109', 'firefox114', 'safari16.4'],
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
