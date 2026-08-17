import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true
  },
  build: {
    rollupOptions: {
      output: {
        // Тяжёлые библиотеки — в отдельные vendor-чанки. recharts и
        // framer-motion нужны только внутри отчёта (ленивые секции), поэтому
        // их чанки подтягиваются вместе с секцией, а не грузятся при первом
        // открытии приложения. react выносится ради кэширования: он меняется
        // редко, и браузер переиспользует его между деплоями.
        manualChunks: {
          'vendor-react': ['react', 'react-dom'],
          'vendor-charts': ['recharts'],
          'vendor-motion': ['framer-motion'],
        },
      },
    },
  },
})
