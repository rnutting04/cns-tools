import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Use esbuild's automatic JSX runtime (React 19) for tests. We don't need
  // @vitejs/plugin-react here — that plugin is for dev HMR/fast-refresh, not tests.
  esbuild: {
    jsx: 'automatic',
    jsxImportSource: 'react',
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    coverage: {
      provider: 'v8',
      reportsDirectory: './coverage',
      reporter: ['text', 'html'],
      exclude: [
        'src/main.tsx',
        'src/**/*.test.{ts,tsx}',
        'src/test/**',
        '**/*.config.*',
        'src/types/**',
      ],
    },
  },
})
