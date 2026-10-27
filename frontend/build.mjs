import * as esbuild from 'esbuild';
import { copyFile, mkdir, stat } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

/**
 * Builds the React console into the Python app's static directory.
 *
 *   frontend/src/*  ->  web/static/app.js + web/static/app.css
 *
 * The Python server stays dependency-free: it just serves these two files.
 * Run `npm run build` (or `npm run watch`) after touching src/.
 */

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(here, '../web/static');
const watch = process.argv.includes('--watch');

await mkdir(outDir, { recursive: true });

/** @type {import('esbuild').BuildOptions} */
const options = {
  entryPoints: [resolve(here, 'src/main.jsx')],
  outfile: resolve(outDir, 'app.js'),
  bundle: true,
  format: 'iife',
  target: ['es2020', 'chrome100', 'safari15', 'firefox100'],
  jsx: 'automatic',
  loader: { '.js': 'jsx' },
  minify: !watch,
  sourcemap: true,
  legalComments: 'none',
  logLevel: 'info',
  define: { 'process.env.NODE_ENV': '"production"' },
  // The Libraries.dev packages are ESM and side-effect free; nothing exotic needed.
  mainFields: ['module', 'main'],
};

if (watch) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log('watching frontend/src -> web/static/app.js');
} else {
  await esbuild.build(options);
  // index.html lives beside the bundle so the Python server can serve it as-is.
  await copyFile(resolve(here, 'index.html'), resolve(outDir, 'index.html'));
  const { size } = await stat(resolve(outDir, 'app.js'));
  console.log(`built web/static/app.js (${(size / 1024).toFixed(0)} kB) + app.css + index.html`);
}
