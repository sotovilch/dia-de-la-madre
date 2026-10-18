// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  // Compatible with GitHub Pages repository deployment
  site: process.env.SITE_URL || 'https://sotovilch.github.io',
  base: process.env.BASE_PATH || '/dia-de-la-madre',
  build: {
    assets: '_astro',
  },
});
