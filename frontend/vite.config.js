import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  // 把依赖预构建缓存写到本地磁盘，避免 OneDrive 同步盘上 Vite 卡死
  cacheDir: 'C:/mockwise_vite_cache',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 讯飞语音转写 WebSocket
      '/ws': {
        target: 'http://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
      },
      // 简历等上传文件
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // 把大体积三方库拆成独立 chunk，便于浏览器长缓存，并消除体积告警
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          'vue-vendor': ['vue', 'vue-router', 'pinia'],
          'antd-vendor': ['ant-design-vue'],
          'echarts-vendor': ['echarts'],
        },
      },
    },
  },
})
