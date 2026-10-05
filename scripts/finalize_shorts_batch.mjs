// Assemble already-authored frames; no provider calls or voice regeneration.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
function option(name) {
  const i = args.indexOf(name);
  if (i < 0 || !args[i + 1]) throw new Error(`Required: ${name}`);
  return path.resolve(args[i + 1]);
}
const manifest = JSON.parse(fs.readFileSync(option('--creative'), 'utf8'));
const skills = option('--skills-root');
const core = option('--core-project');
function run(script, ...flags) {
  const result = spawnSync(process.execPath, [path.join(skills, script), ...flags], {
    cwd: root, stdio: 'inherit', shell: false,
  });
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${script} exited ${result.status}`);
}
for (const episode of manifest.episodes) {
  const project = path.resolve(root, episode.project);
  if (!project.startsWith(path.join(root, 'videos') + path.sep)) throw new Error('Project escapes videos/');
  const storyboard = path.join(project, 'STORYBOARD.md');
  const meta = path.join(project, 'audio_meta.json');
  const frame = path.join(project, 'compositions/frames/01-explainer.html');
  if (!fs.existsSync(frame)) throw new Error(`${episode.id}: author the frame first`);
  fs.writeFileSync(storyboard, fs.readFileSync(storyboard, 'utf8').replace('- status: outline', '- status: animated'));
  run('faceless-explainer/scripts/captions.mjs', 'build', '--storyboard', storyboard,
    '--audio-meta', meta, '--hyperframes', project, '--out', path.join(project, 'caption_groups.json'));
  run('faceless-explainer/scripts/assemble-index.mjs', '--storyboard', storyboard, '--hyperframes', project);
  const index = path.join(project, 'index.html');
  let html = fs.readFileSync(index, 'utf8');
  html = html.replace(/(<[^>]+data-composition-src="compositions\/captions\.html")/, '$1 data-track-kind="captions"');
  fs.writeFileSync(index, html);
  run('faceless-explainer/scripts/transitions.mjs', 'inject', '--storyboard', storyboard, '--hyperframes', project);
  run('faceless-explainer/scripts/transitions.mjs', 'verify', '--storyboard', storyboard, '--index', index);
  run('hyperframes-audio/scripts/carve.mjs', '--comp', index, '--core', core,
    '--bed', 'el-bgm', '--voice', 'el-01-explainer-voice');
  console.log(`${episode.id}: captions, timeline and voice-aware music assembled`);
}
