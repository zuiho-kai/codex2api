"""Restore the retained n150 deployment with current gateway credentials."""
import datetime
import json
import os
import pathlib
import shutil
import sqlite3
import subprocess
import time
import urllib.request

os.umask(0o077)
old = pathlib.Path('/root/migration-gpt-load-20261008-015011/retired/opt-codex2api')
target = pathlib.Path('/opt/codex2api')
volume = pathlib.Path('/var/lib/docker/volumes/codex2api-sqlite_sqlite-data/_data')
gvolume = pathlib.Path('/var/lib/docker/volumes/gpt-load_gpt-load-data/_data')
backup = pathlib.Path('/root/restore-codex2api-' + datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
backup.mkdir(mode=0o700)
base = 'http://100.106.164.88:8080'
env = dict(line.split('=', 1) for line in pathlib.Path('/opt/gpt-load/.env').read_text().splitlines() if '=' in line)

def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)

def api(path, post=False):
    req = urllib.request.Request(base + path, data=b'{}' if post else None,
        headers={'Authorization': 'Bearer ' + env['AUTH_KEY'], 'Content-Type': 'application/json'})
    result = json.load(urllib.request.urlopen(req, timeout=30))
    assert result.get('code') == 0, 'GPT-Load export rejected'
    return result['data']

assert old.is_dir() and (volume / 'codex2api.db').is_file()
assert not target.exists(), 'Existing target requires inspection; refusing overwrite'
run('docker', 'image', 'inspect', 'codex2api:gpt6-price-sync-20261005')
exports = {gid: api(f'/api/groups/{gid}/credentials/download-all', True)['files'] for gid in (1, 2)}
assert all(len(files) == 1 for files in exports.values())
models = api('/api/groups/1/models')['items']
shutil.copytree(old, target)
stopped = False
started = False
try:
    run('docker', 'stop', 'gpt-load-gpt-load-1')
    stopped = True
    shutil.copytree(gvolume, backup / 'gpt-load-data')
    shutil.copytree(volume, backup / 'codex2api-data')
    (backup / 'exports.json').write_text(json.dumps(exports))
    gc = sqlite3.connect('file:' + str(gvolume / 'gpt-load.db') + '?mode=ro', uri=True)
    gc.row_factory = sqlite3.Row
    db = sqlite3.connect(volume / 'codex2api.db')
    for gid, aid in [(1, 5), (2, 6)]:
        source = exports[gid][0]['credential']
        creds = json.loads(db.execute('select credentials from accounts where id=?', (aid,)).fetchone()[0])
        assert source.get('email') == creds.get('email'), 'Account mismatch'
        for key in ('access_token', 'refresh_token', 'id_token', 'account_id', 'email', 'project_id'):
            if source.get(key):
                creds[key] = source[key]
        if source.get('expired'):
            creds['expires_at'] = source['expired']
        if gid == 1:
            creds['models'] = sorted(set(item['id'] for item in models))
        db.execute('update accounts set credentials=?, enabled=1, status=?, cooldown_reason=?, cooldown_until=NULL, error_message=?, updated_at=CURRENT_TIMESTAMP where id=?',
            (json.dumps(creds), 'active', '', '', aid))
    for row in gc.execute("select name,key_value,status,filters,expires_at_ms from access_keys"):
        exists = db.execute('select id from api_keys where key=?', (row['key_value'],)).fetchone()
        if exists:
            continue
        filters = json.loads(row['filters'] or '{}')
        assert not filters.get('models') and not filters.get('protocols'), 'Restricted key needs explicit translation'
        groups = filters.get('groups', [])
        limits = {'upstream_channel': 'antigravity' if groups == [1] else 'codex' if groups == [2] else 'auto'}
        assert groups in ([1], [2], [1, 2]), 'Unknown key scope'
        assert not row['expires_at_ms'], 'Expiring key needs explicit translation'
        db.execute('insert into api_keys(name,key,quota_limit,quota_used,total_used,reset_count,allowed_group_ids,enabled,created_at,limits) values(?,?,0,0,0,0,?,?,CURRENT_TIMESTAMP,?)',
            (row['name'], row['key_value'], '[]', int(row['status'] == 'active'), json.dumps(limits)))
    db.commit()
    assert db.execute('pragma integrity_check').fetchone()[0] == 'ok'
    db.close()
    gc.close()
    run('docker', 'compose', '-f', str(target / 'docker-compose.yml'), '--env-file', str(target / '.env'), 'up', '-d', '--pull', 'never')
    started = True
    for _ in range(30):
        try:
            with urllib.request.urlopen(base + '/health', timeout=3) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError('codex2api health check failed')
    (backup / 'result.json').write_text(json.dumps({'commit': os.getenv('GITHUB_SHA'), 'image': 'codex2api:gpt6-price-sync-20261005', 'status': 'healthy'}))
    run('docker', 'update', '--restart=no', 'gpt-load-gpt-load-1')
    print('RESTORED codex2api; BACKUP=' + str(backup))
except Exception:
    if not started and stopped:
        # No new token owner ran: restarting the previous owner is safe.
        run('docker', 'start', 'gpt-load-gpt-load-1')
    raise
