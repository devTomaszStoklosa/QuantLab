import { fileURLToPath } from 'node:url';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The QuantForge design system lives next to this app, in presentation/design-system.
const designSystem = fileURLToPath(new URL('../design-system/project', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@design-system': designSystem } },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:5080' },
    fs: { allow: ['..'] },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
