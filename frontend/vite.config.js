import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 代理 /generate 和 /health 到后端
    proxy: {
      '/generate': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    }
  }
})
