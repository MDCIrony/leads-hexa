import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Backend origin: same default as verify-e2e.sh and the Bruno collection.
const backendOrigin = process.env.VITE_API_BASE_URL || 'http://localhost:8001';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': backendOrigin,
    },
  },
});
