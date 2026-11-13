"""Explicit first-run cloud initialization; never replace an operational database."""
import os
import sqlite3
from contextlib import closing
from pathlib import Path
import storage

def initialize_cloud():
    destination=storage.DATABASE_PATH
    source=destination.parent/'incoming.sqlite3'
    marker=destination.parent/'.drive-import-completed'
    if os.environ.get('WEFIX_IMPORT_STAGED_DB')=='true' and not marker.exists():
        if not source.is_file(): raise RuntimeError('Archivio di importazione non disponibile')
        if destination.exists():
            with closing(sqlite3.connect(destination)) as current:
                names={row[0] for row in current.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                for table in ('snapshots','prices','catalog_prices','jobs'):
                    if table in names and current.execute('SELECT count(*) FROM '+table).fetchone()[0]:
                        raise RuntimeError('Archivio cloud non vuoto: importazione automatica rifiutata')
        destination.parent.mkdir(parents=True,exist_ok=True)
        temporary=destination.with_suffix('.incoming')
        with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True)) as src:
            if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Archivio sorgente non integro')
            with closing(sqlite3.connect(temporary)) as dst:
                src.backup(dst)
                if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Copia non integra')
        # Startup runs before HTTP processes open the database.
        for suffix in ('-wal','-shm'):
            Path(str(destination)+suffix).unlink(missing_ok=True)
        os.replace(temporary,destination)
        marker.write_text('Imported from authorized Drive history\n')
    if not destination.exists() and os.environ.get('WEFIX_INITIALIZE_EMPTY')!='true':
        raise RuntimeError('Confermare inizializzazione del nuovo archivio cloud')
    storage.init_db()
