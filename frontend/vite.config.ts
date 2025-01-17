import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // 이렇게 하면 0.0.0.0으로 바인딩됩니다
    port: 3000,
  },
  resolve: {
    alias: {
    },
  },
})