#!/usr/bin/env node
// Capture only source-owned local thumbnail HTML; no connected browser/user tabs.
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {pathToFileURL} from 'node:url';

const arg = process.argv.indexOf('--creative');
if (arg < 0 || !process.argv[arg + 1]) throw new Error('Required: --creative <file>');
const spec = JSON.parse(fs.readFileSync(process.argv[arg + 1], 'utf8'));
const chrome = process.env.HYPERFRAMES_BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe';
if (!fs.existsSync(chrome)) throw new Error('Set HYPERFRAMES_BROWSER_PATH to an installed Chrome');
const onlyIndex = process.argv.indexOf('--only');
const only = onlyIndex >= 0 ? process.argv[onlyIndex + 1] : null;
for (const ep of spec.episodes) {
  if (only && only !== ep.id) continue;
  const project = path.resolve(ep.project);
  const videos = path.resolve('videos') + path.sep;
  if (!project.startsWith(videos)) throw new Error('Project escapes videos/');
  const input = path.join(project, 'THUMBNAIL.html');
  const output = path.join(project, 'assets/thumbnails/thumbnail.png');
  if (!fs.existsSync(input)) throw new Error(`${ep.id}: build thumbnail HTML first`);
  fs.mkdirSync(path.dirname(output), {recursive:true});
  const profile = path.join(project, '.hyperframes/thumbnail-profile');
  const result = spawnSync(chrome, [
    '--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
    '--run-all-compositor-stages-before-draw', '--virtual-time-budget=2500',
    `--user-data-dir=${profile}`, `--window-size=${ep.format === 'shorts' ? '1080,1920' : '1280,720'}`,
    `--screenshot=${output}`, pathToFileURL(input).href,
  ], {encoding:'utf8', windowsHide:true, timeout:90000});
  if (result.error || result.status !== 0 || !fs.existsSync(output) || !fs.statSync(output).size) {
    throw new Error(`${ep.id}: thumbnail capture failed: ${result.error?.message ?? result.stderr?.slice(-1000)}`);
  }
  console.log(`${ep.id}: ${output}`);
}
