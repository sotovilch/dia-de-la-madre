// @ts-check
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
  // Compatible with both root domain and GitHub Pages subfolder deployment
  site: process.env.SITE_URL || 'https://gersoto3110.github.io',
  base: process.env.BASE_PATH || undefined,
  build: {
    assets: '_astro',
  },
});
