"""Esporta una copia coerente dell'archivio senza modificare l'originale."""
import argparse, shutil, sqlite3
from contextlib import closing
from pathlib import Path

def export(source, directory):
    source=Path(source).resolve(strict=True)
    directory=Path(directory).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    dest=directory/'wefix_prices.sqlite3'
    if dest.exists(): raise FileExistsError('Esportazione gia presente; non viene sovrascritta')
    with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro',uri=True)) as src:
        if src.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Archivio sorgente non integro')
        if src.execute("SELECT count(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]: raise ValueError('Un lavoro e ancora attivo')
        target=sqlite3.connect(dest)
        try: src.backup(target)
        finally: target.close()
    with closing(sqlite3.connect(dest)) as db:
        if db.execute("SELECT count(*) FROM jobs WHERE status IN ('running','queued')").fetchone()[0]:
            raise ValueError('Un lavoro e iniziato durante la copia; esportazione non utilizzabile')
        rows=db.execute('SELECT id,log_file FROM jobs').fetchall()
        log_root=(source.parent/'jobs').resolve()
        for job,old in rows:
            if not old: continue
            path=Path(old).resolve()
            new=directory/'jobs'/f'{job}.log'
            if path.is_relative_to(log_root) and path.is_file():
                new.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,new)
            db.execute('UPDATE jobs SET log_file=? WHERE id=?',(f'/app/data/jobs/{job}.log',job))
        counts={name:db.execute(f'SELECT count(*) FROM {name}').fetchone()[0] for name in ('snapshots','prices','jobs')}
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError('Copia non integra')
        db.commit()
        if db.execute('PRAGMA journal_mode=DELETE').fetchone()[0].lower() != 'delete':
            raise ValueError('Impossibile creare una copia SQLite autonoma')
    return counts

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source');parser.add_argument('directory')
    args=parser.parse_args();print(export(args.source,args.directory))
