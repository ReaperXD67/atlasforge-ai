"""Download returned V3 artifacts from an ignored private URL ledger.

This does not call generation APIs, spend credits, or modify existing sources.
Run inspect_sources_v3.py after download for full decoding and frame samples.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from prepare_film import read_json, sha256, write_json

ROOT = Path(__file__).resolve().parent
DIRECTORY = ROOT / 'assets/native-v3'


def download(item):
    path = (ROOT / item['path']).resolve()
    if not path.is_relative_to(DIRECTORY.resolve()) or path.suffix != '.mp4':
        raise ValueError('V3 artifact must stay in assets/native-v3 as an MP4.')
    if not item['url'].startswith('https://'):
        raise ValueError('Expected the returned HTTPS artifact URL.')
    receipt = path.with_suffix('.download.json')
    url_hash = hashlib.sha256(item['url'].encode()).hexdigest()
    if path.exists():
        recorded = read_json(receipt) if receipt.exists() else {}
        if recorded.get('task_id') != item['task_id'] or recorded.get('sha256') != sha256(path):
            raise ValueError(f'Existing source does not match its receipt: {item["id"]}')
        return {'id': item['id'], 'status': 'reused_verified_local_file'}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.download.part')
    request = urllib.request.Request(item['url'], headers={'User-Agent': 'AtlasForge-V3/1.0'})
    with urllib.request.urlopen(request, timeout=120) as response, temporary.open('wb') as out:
        for block in iter(lambda: response.read(1024 * 1024), b''):
            out.write(block)
    if temporary.stat().st_size == 0:
        raise ValueError(f'Empty artifact: {item["id"]}')
    temporary.replace(path)
    write_json(receipt, {'id': item['id'], 'task_id': item['task_id'],
                        'url_sha256': url_hash, 'sha256': sha256(path),
                        'bytes': path.stat().st_size})
    return {'id': item['id'], 'status': 'downloaded', 'bytes': path.stat().st_size}


def main():
    ledger = read_json(DIRECTORY / 'provider-record.private.json')
    outputs = ledger.get('outputs', [])
    if len({x['id'] for x in outputs}) != len(outputs):
        raise ValueError('Duplicate artifact IDs in private ledger.')
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(download, outputs):
            print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
