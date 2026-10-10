#!/usr/bin/env node
// Finish authored tracks using HyperFrames' public, voice-aware audio analysis.
// This never changes speech, calls a provider, or reassembles visual compositions.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
function option(name) {
  const index = args.indexOf(name);
  if (index < 0 || !args[index + 1] || args[index + 1].startsWith('--')) {
    throw new Error(`Required: ${name}`);
  }
  return path.resolve(root, args[index + 1]);
}
const creative = JSON.parse(fs.readFileSync(option('--creative'), 'utf8'));
const carve = path.join(option('--skills-root'), 'hyperframes-audio/scripts/carve.mjs');
const core = option('--core-project');
if (!fs.existsSync(carve)) throw new Error('Install the HyperFrames audio skill first');
if (!fs.existsSync(path.join(core, 'node_modules/@hyperframes/core/package.json'))) {
  throw new Error('Install the pinned @hyperframes/core in --core-project first');
}
for (const episode of creative.episodes) {
  const project = path.resolve(root, episode.project);
  const relative = path.relative(path.join(root, 'videos'), project);
  if (!relative || relative.startsWith('..') || path.isAbsolute(relative)) {
    throw new Error(`${episode.id}: project escapes a child of videos/`);
  }
  const comp = path.join(project, 'index.html');
  if (!fs.existsSync(comp)) throw new Error(`${episode.id}: build compositions first`);
  const result = spawnSync(process.execPath, [
    carve, '--comp', comp, '--core', core, '--bed', 'bgm', '--voice', 'voiceover',
  ], {cwd: root, stdio: 'inherit', shell: false, windowsHide: true});
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${episode.id}: carving failed (${result.status})`);
  console.log(`${episode.id}: music carved against the unchanged narration`);
}
