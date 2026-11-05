"""Coda locale: ogni esecuzione viene affidata al massimo una volta."""
from __future__ import annotations
from pathlib import Path
import time
import storage

ACTIONS = {'sale','trade_all','all_scrapers','import_history', *(f'trade_{i}' for i in range(1,7))}

def enqueue(action):
    if action not in ACTIONS:
        raise ValueError('Comando non autorizzato')
    filename = storage.BASE_DIR / 'data' / 'jobs' / f'{time.time_ns()}_{action}.log'
    return storage.new_job(action, filename)

def claim():
    with storage.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        job = db.execute("SELECT id,action FROM jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if job is None:
            return None
        db.execute("UPDATE jobs SET status='running' WHERE id=? AND status='queued'", (job['id'],))
        return {'id':job['id'], 'action':job['action']}

def append_log(job_id, text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 65536:
        raise ValueError('Log non valido')
    with storage.connection() as db:
        row = db.execute("SELECT log_file FROM jobs WHERE id=? AND status='running'",(job_id,)).fetchone()
    if not row:
        raise ValueError('Esecuzione non attiva')
    root = (storage.BASE_DIR / 'data' / 'jobs').resolve()
    path = Path(row['log_file']).resolve()
    if not path.is_relative_to(root):
        raise ValueError('Percorso log non valido')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a',encoding='utf-8') as f:
        f.write(text)

def request_continue(job_id):
    with storage.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT id FROM jobs WHERE id=? AND status='running'",(job_id,)).fetchone()
        if not row: raise ValueError('Esecuzione non attiva')
        db.execute('INSERT INTO job_inputs(job_id,pending) VALUES (?,1) ON CONFLICT(job_id) DO UPDATE SET pending=1',(job_id,))

def take_continue(job_id):
    with storage.connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT pending FROM job_inputs JOIN jobs ON jobs.id=job_inputs.job_id WHERE job_id=? AND jobs.status='running'",(job_id,)).fetchone()
        if row and row['pending']:
            db.execute('UPDATE job_inputs SET pending=0 WHERE job_id=?',(job_id,))
            return True
        return False

def finish(job_id, exit_code, error=None):
    if type(exit_code) is not int:
        raise ValueError('Esito non valido')
    with storage.connection() as db:
        cursor=db.execute("""UPDATE jobs SET status=?, exit_code=?, error=?, finished_at=CURRENT_TIMESTAMP
                            WHERE id=? AND status='running'""",
                          ('completed' if exit_code==0 else 'failed',exit_code,error,job_id))
        if cursor.rowcount != 1:
            existing=db.execute('SELECT status,exit_code FROM jobs WHERE id=?',(job_id,)).fetchone()
            expected='completed' if exit_code==0 else 'failed'
            if not existing or existing['status'] != expected or existing['exit_code'] != exit_code:
                raise ValueError('Esecuzione non attiva')
