"""Archivio SQLite condiviso, locale e indipendente dagli scraper."""
from __future__ import annotations

import os
import re
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("WEFIX_DB_PATH") or BASE_DIR / "data" / "wefix_prices.sqlite3").expanduser()

@contextmanager
def connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH, timeout=40)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=40000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()

def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
          id INTEGER PRIMARY KEY,
          kind TEXT NOT NULL CHECK(kind IN ('sale','tradein')),
          source_id TEXT NOT NULL,
          filename TEXT NOT NULL,
          sheet_name TEXT NOT NULL,
          is_primary INTEGER NOT NULL DEFAULT 0,
          content_hash TEXT,
          scanned_at TEXT NOT NULL,
          folder_name TEXT,
          source_url TEXT,
          imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          record_count INTEGER NOT NULL DEFAULT 0,
          UNIQUE(kind, source_id, sheet_name)
        );
        CREATE TABLE IF NOT EXISTS prices (
          id INTEGER PRIMARY KEY,
          snapshot_id INTEGER NOT NULL REFERENCES snapshots(id) ON DELETE CASCADE,
          model TEXT NOT NULL,
          model_key TEXT NOT NULL,
          color TEXT NOT NULL,
          color_key TEXT NOT NULL,
          storage_gb INTEGER NOT NULL,
          price_eur REAL NOT NULL CHECK(price_eur > 0),
          UNIQUE(snapshot_id,model_key,color_key,storage_gb)
        );
        CREATE INDEX IF NOT EXISTS ix_prices_lookup ON prices(model_key, storage_gb, color_key);
        CREATE INDEX IF NOT EXISTS ix_snapshots_time ON snapshots(kind,scanned_at);
        CREATE TABLE IF NOT EXISTS jobs (
          id INTEGER PRIMARY KEY,
          action TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'queued',
          started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          finished_at TEXT,
          exit_code INTEGER,
          log_file TEXT,
          pid INTEGER,
          error TEXT
        );
        """)
        columns = {r[1] for r in db.execute("PRAGMA table_info(snapshots)")}
        if "is_primary" not in columns:
            db.execute("ALTER TABLE snapshots ADD COLUMN is_primary INTEGER NOT NULL DEFAULT 0")
        if "content_hash" not in columns:
            db.execute("ALTER TABLE snapshots ADD COLUMN content_hash TEXT")

def _clean(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()

def _key(s):
    return _clean(s).casefold()

def parse_price(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return round(number, 2) if 0 < number < 100000 else None
    text = _clean(value).replace("\u00a0", "").replace("€", "").replace("EUR", "").strip()
    if not text or _key(text) in {"inesistente", "nan", "none", "null", "n.d.", "n/a", "-", "—", "#n/d", "non disponibile"}:
        return None
    text = re.sub(r"[^\d.,-]", "", text)
    if not text:
        return None
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif text.count(".") > 1:
        text = text.replace(".", "")
    try:
        number = float(text)
        return round(number, 2) if 0 < number < 100000 else None
    except ValueError:
        return None

def storage_to_gb(header):
    match = re.match(r"^\s*(\d+)\s*(TB|GB)\s*$", str(header or ""), flags=re.I)
    if match:
        return int(match.group(1)) * (1024 if match.group(2).upper() == "TB" else 1)
    return None

def parse_scanned_at(name, fallback=None):
    """Legge YYYYMMDD_HHMMSS, YYYY-MM-DD_HH-MM-SS, DD-MM-YYYY_HH-MM-SS."""
    text = str(name or "")
    matches = [
        (r"(20\d{2})(\d{2})(\d{2})[_ -](\d{2})(\d{2})(\d{2})", "%Y%m%d%H%M%S"),
        (r"(20\d{2})-(\d{2})-(\d{2})[_ -](\d{2})[-:](\d{2})[-:](\d{2})", "%Y%m%d%H%M%S"),
        (r"(\d{2})-(\d{2})-(20\d{2})[_ -](\d{2})[-:](\d{2})[-:](\d{2})", "%d%m%Y%H%M%S"),
    ]
    for regex, fmt in matches:
        m = re.search(regex, text)
        if m:
            try:
                return datetime.strptime("".join(m.groups()), fmt).strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                continue
    if fallback:
        try:
            return datetime.fromisoformat(str(fallback).replace("Z", "+00:00")).strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            pass
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def _extract_prices(rows):
    """Rileva l'intestazione effettiva nelle prime 12 righe, anche dopo la data."""
    rows = [list(row) for row in rows]
    for h_idx, header in enumerate(rows[:12]):
        cols = [_key(x) for x in header]
        model_idx = next((i for i, x in enumerate(cols) if x in {"modello", "modelli", "model"}), None)
        color_idx = next((i for i, x in enumerate(cols) if x in {"colori", "colore", "color"}), None)
        if model_idx is None or color_idx is None:
            continue
        capacities = [(i, storage_to_gb(c)) for i, c in enumerate(header)]
        capacities = [(i, gb) for i, gb in capacities if gb is not None]
        if not capacities:
            continue
        records = {}
        for row in rows[h_idx + 1:]:
            model = _clean(row[model_idx] if len(row) > model_idx else "")
            color = _clean(row[color_idx] if len(row) > color_idx else "")
            if not model or _key(model).startswith(("aggiornato il:", "data e ora di estrazione:")):
                continue
            for i, gb in capacities:
                value = parse_price(row[i] if i < len(row) else None)
                if value is not None:
                    records[(_key(model), _key(color), gb)] = (model, color, gb, value)
        return list(records.values())
    return []

def import_rows(rows, *, kind, source_id, filename, sheet_name, scanned_at, folder_name="", source_url="", is_primary=False):
    if kind not in {"sale", "tradein"}:
        raise ValueError("Tipo prezzi non supportato")
    records = _extract_prices(rows)
    if not records:
        raise ValueError(f"Nessun prezzo valido trovato in {filename} / {sheet_name}")
    content_hash = hashlib.sha256(repr(sorted(records)).encode("utf-8")).hexdigest()
    init_db()
    with connection() as db:
        old = db.execute("SELECT id,content_hash FROM snapshots WHERE kind=? AND source_id=? AND sheet_name=?",
                         (kind,source_id,sheet_name)).fetchone()
        if old and old["content_hash"] == content_hash:
            return {"status": "skipped", "count": len(records), "snapshot_id": old["id"]}
        if old:
            snapshot_id = old["id"]
            db.execute("DELETE FROM prices WHERE snapshot_id=?", (snapshot_id,))
            db.execute("""UPDATE snapshots SET filename=?, scanned_at=?,folder_name=?,source_url=?,record_count=?,is_primary=?,content_hash=?
                       WHERE id=?""", (filename,scanned_at,folder_name,source_url,len(records),int(is_primary),content_hash,snapshot_id))
        else:
            cursor = db.execute("""INSERT INTO snapshots
              (kind,source_id,filename,sheet_name,scanned_at,folder_name,source_url,record_count,is_primary,content_hash)
              VALUES(?,?,?,?,?,?,?,?,?,?)""",
              (kind,source_id,filename,sheet_name,scanned_at,folder_name,source_url,len(records),int(is_primary),content_hash))
            snapshot_id = cursor.lastrowid
        db.executemany("""INSERT INTO prices
          (snapshot_id,model,model_key,color,color_key,storage_gb,price_eur)
          VALUES (?,?,?,?,?,?,?)""",
          [(snapshot_id,m,_key(m),c,_key(c),g,p) for m,c,g,p in records])
    return {"status": "imported", "count": len(records), "snapshot_id": snapshot_id}

def import_xlsx(path, *, kind, source_id=None, scanned_at=None, source_url="", folder_name=""):
    from openpyxl import load_workbook
    path = Path(path)
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        selected = sorted(wb.sheetnames, key=lambda s: (s.casefold() != "apple", s))
        results = []
        for sheet in selected:
            try:
                results.append(import_rows(list(wb[sheet].values), kind=kind,
                    source_id=source_id or f"local:{kind}:{path.name}",
                    filename=path.name, sheet_name=sheet,
                    scanned_at=scanned_at or parse_scanned_at(path.stem),
                    folder_name=folder_name or path.parent.name,
                    source_url=source_url,
                    is_primary=(sheet.casefold() == "apple" or not results)))
            except ValueError:
                continue
        if not results:
            raise ValueError(f"Nessun foglio con prezzi riconosciuto in {path.name}")
        return {"status": "imported" if any(r["status"]=="imported" for r in results) else "skipped",
                "count":sum(r["count"] for r in results), "sheets":len(results)}
    finally:
        wb.close()

def frame(query, params=()):
    import pandas as pd
    init_db()
    with connection() as db:
        return pd.read_sql_query(query, db, params=params)

def latest_prices(kind, sheet_name=None):
    return frame("""
      WITH ranked AS (
        SELECT p.*,s.scanned_at,s.filename,s.source_url,
          ROW_NUMBER() OVER (PARTITION BY p.model_key,p.color_key,p.storage_gb
            ORDER BY s.scanned_at DESC,s.id DESC) AS rn
        FROM prices p JOIN snapshots s ON s.id=p.snapshot_id
        WHERE s.kind=? AND (? IS NOT NULL AND lower(s.sheet_name)=lower(?) OR ? IS NULL AND s.is_primary=1)
      )
      SELECT model,color,storage_gb,price_eur,scanned_at,filename,source_url,model_key,color_key
      FROM ranked WHERE rn=1 ORDER BY model,storage_gb,color
    """, (kind, sheet_name, sheet_name, sheet_name))

def history(kind, model_key, storage_gb, color_key=None, sheet_name=None):
    query = """SELECT s.scanned_at,p.price_eur,p.color,s.filename,s.source_url
      FROM prices p JOIN snapshots s ON s.id=p.snapshot_id
      WHERE s.kind=? AND p.model_key=? AND p.storage_gb=?
        AND (? IS NOT NULL AND lower(s.sheet_name)=lower(?) OR ? IS NULL AND s.is_primary=1)"""
    args = [kind, model_key, int(storage_gb), sheet_name, sheet_name, sheet_name]
    if color_key:
        query += " AND p.color_key=?"
        args.append(color_key)
    query += " ORDER BY s.scanned_at"
    return frame(query, tuple(args))

def snapshots():
    return frame("""SELECT s.kind,s.source_id,s.scanned_at,s.filename,s.folder_name,s.sheet_name,
       s.is_primary,s.record_count,s.source_url,s.imported_at FROM snapshots s
       ORDER BY s.scanned_at DESC,s.id DESC""")

def jobs():
    return frame("SELECT * FROM jobs ORDER BY id DESC LIMIT 100")

def new_job(action, log_file):
    init_db()
    with connection() as db:
        running = db.execute("SELECT id FROM jobs WHERE status IN ('queued','running') LIMIT 1").fetchone()
        if running:
            raise RuntimeError(f"Un'altra esecuzione è in corso (ID {running['id']}).")
        return db.execute("INSERT INTO jobs(action,log_file) VALUES(?,?)", (action,str(log_file))).lastrowid

def update_job(job_id, *, status, exit_code=None, pid=None, error=None):
    with connection() as db:
        db.execute("""UPDATE jobs SET status=?,exit_code=?,pid=?,error=?,
           finished_at=CASE WHEN ? IN ('completed','failed') THEN CURRENT_TIMESTAMP ELSE NULL END
           WHERE id=?""", (status,exit_code,pid,error,status,job_id))
