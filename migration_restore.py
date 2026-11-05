"""Prima inizializzazione del volume, soltanto se il DB non esiste."""
import os, shutil, sqlite3
from contextlib import closing
from pathlib import Path

def restore(source=Path('/migration/wefix_prices.sqlite3'), destination=Path('/app/data/wefix_prices.sqlite3')):
    if destination.exists(): return False
    if not source.is_file(): raise FileNotFoundError('Copia iniziale del database non disponibile')
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix('.initializing')
    if temporary.exists(): raise RuntimeError('Ripristino interrotto: verifica richiesta')
    with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True)) as src:
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('Copia non integra')
        with closing(sqlite3.connect(temporary)) as dest:
            src.backup(dest)
            if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok': raise ValueError('DB importato non integro')
            for table in ('snapshots','prices','jobs'):
                if src.execute(f'SELECT count(*) FROM {table}').fetchone()!=dest.execute(f'SELECT count(*) FROM {table}').fetchone():
                    raise ValueError('Conteggi non coerenti')
    logs=source.parent/'jobs'
    if logs.is_dir(): shutil.copytree(logs,destination.parent/'jobs',dirs_exist_ok=True)
    os.replace(temporary,destination)
    return True
