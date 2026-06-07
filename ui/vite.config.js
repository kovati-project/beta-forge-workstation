import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8800',
      '/status': 'http://localhost:8800',
      '/loadouts': 'http://localhost:8800',
      '/activate': 'http://localhost:8800',
      '/stop': 'http://localhost:8800',
      '/health': 'http://localhost:8800',
    }
  },
  build: {
    outDir: '../loadout-manager/static',
    emptyOutDir: true,
  }
});
