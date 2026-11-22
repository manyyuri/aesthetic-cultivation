import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    // 用正则精确匹配：字符串别名会把 "@ac/ui" 前缀匹配到 "@ac/ui/tokens.css" 上
    alias: [
      { find: /^@ac\/ui\/tokens\.css$/, replacement: fileURLToPath(new URL('../../packages/ui/src/tokens.css', import.meta.url)) },
      { find: /^@ac\/ui$/, replacement: fileURLToPath(new URL('../../packages/ui/src/tokens.ts', import.meta.url)) },
    ],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8710', changeOrigin: true },
      '/metrics': { target: 'http://127.0.0.1:8710', changeOrigin: true },
    },
  },
  test: { environment: 'jsdom', globals: true },
});
