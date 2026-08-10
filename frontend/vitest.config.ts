import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

// A separate file, not a `test` block inside vite.config.ts: Vite's own
// `defineConfig` type has no `test` property, and tsconfig.json only
// includes `src`/`tests` so `tsc --noEmit` never sees that file anyway — but
// the editor does. `vitest/config` re-exports `defineConfig` typed with the
// `test` key merged in, so this stays type-checked without reaching for a
// triple-slash reference.
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
    },
  })
);
