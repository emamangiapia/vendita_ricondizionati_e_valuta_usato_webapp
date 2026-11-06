"""Listini pubblicati e proposte, separati dalle rilevazioni originali."""
import math
import re
import sqlite3

KINDS = ('tradein', 'sale')
DEFAULT_AUTOMATIC_LIMIT = 10.0
AUTOMATIC_DEFAULT_MIGRATION = 'automatic_default_v1'

def init(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS catalog_state (kind TEXT PRIMARY KEY, initialized INTEGER NOT NULL DEFAULT 0, mode TEXT NOT NULL DEFAULT 'manual', up_limit REAL, down_limit REAL);
    CREATE TABLE IF NOT EXISTS catalog_prices (id INTEGER PRIMARY KEY, kind TEXT NOT NULL, source TEXT NOT NULL, model TEXT NOT NULL, model_key TEXT NOT NULL, color TEXT NOT NULL, color_key TEXT NOT NULL, storage_gb INTEGER NOT NULL, approved REAL, observed REAL, observed_at TEXT, observed_snapshot INTEGER, proposed REAL, dismissed REAL, UNIQUE(kind, source, model_key, color_key, storage_gb));
    CREATE TABLE IF NOT EXISTS catalog_events (id INTEGER PRIMARY KEY, price_id INTEGER NOT NULL REFERENCES catalog_prices(id), value REAL NOT NULL, status TEXT NOT NULL, actor TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, decided_at TEXT);
    CREATE TABLE IF NOT EXISTS catalog_migrations (name TEXT PRIMARY KEY);
    CREATE TABLE IF NOT EXISTS catalog_notification_reads (event_id INTEGER NOT NULL REFERENCES catalog_events(id), actor TEXT NOT NULL, PRIMARY KEY(event_id, actor));
    ''')
    for kind in KINDS:
        db.execute('INSERT OR IGNORE INTO catalog_state(kind, mode, up_limit, down_limit) VALUES(?, ?, ?, ?)', (kind, 'auto', DEFAULT_AUTOMATIC_LIMIT, DEFAULT_AUTOMATIC_LIMIT))
    # Activate the requested default once, without overriding later manual choices.
    if not db.execute('SELECT 1 FROM catalog_migrations WHERE name=?', (AUTOMATIC_DEFAULT_MIGRATION,)).fetchone():
        db.execute("UPDATE catalog_state SET mode='auto', up_limit=?, down_limit=? WHERE mode='manual'", (DEFAULT_AUTOMATIC_LIMIT, DEFAULT_AUTOMATIC_LIMIT))
        # Existing proposals inside the configured limits no longer need review.
        pending = db.execute('''SELECT e.id AS event_id, e.price_id, e.value, p.approved, p.proposed,
                                      s.up_limit, s.down_limit
                               FROM catalog_events e JOIN catalog_prices p ON p.id=e.price_id
                               JOIN catalog_state s ON s.kind=p.kind
                               WHERE e.status='pending' AND s.mode='auto' AND p.approved > 0
                                 AND p.proposed=e.value AND s.up_limit IS NOT NULL AND s.down_limit IS NOT NULL''').fetchall()
        for row in pending:
            delta = (row['value'] - row['approved']) / row['approved'] * 100
            if -row['down_limit'] <= delta <= row['up_limit']:
                db.execute('UPDATE catalog_prices SET approved=?, proposed=NULL, dismissed=NULL WHERE id=?', (row['value'], row['price_id']))
                db.execute("UPDATE catalog_events SET status='auto', actor='automatico', decided_at=CURRENT_TIMESTAMP WHERE id=?", (row['event_id'],))
        db.execute('INSERT INTO catalog_migrations(name) VALUES(?)', (AUTOMATIC_DEFAULT_MIGRATION,))

def _key(value): return re.sub(r'\s+', ' ', value.strip()).casefold()
def _valid_price(value): return type(value) in (float,int) and math.isfinite(value) and 0 < value < 100000

def reconcile(db, kind):
    """Reconcile only latest observation per product; historical imports cannot roll back state."""
    if kind not in KINDS: raise ValueError('listino non valido')
    state = db.execute('SELECT * FROM catalog_state WHERE kind=?', (kind,)).fetchone()
    rows = db.execute('''WITH ranked AS (
        SELECT p.*, s.scanned_at, s.id AS sid,
          CASE WHEN s.kind='sale' THEN 'principale' ELSE lower(s.sheet_name) END AS source,
          ROW_NUMBER() OVER (PARTITION BY CASE WHEN s.kind='sale' THEN 'principale' ELSE lower(s.sheet_name) END,p.model_key,p.color_key,p.storage_gb ORDER BY s.scanned_at DESC,s.id DESC) AS rn
        FROM prices p JOIN snapshots s ON s.id=p.snapshot_id
        WHERE s.kind=? AND (s.kind='tradein' OR s.is_primary=1)
    ) SELECT * FROM ranked WHERE rn=1''', (kind,)).fetchall()
    if not rows: return
    initial = not state['initialized']
    for r in rows:
        key=(kind,r['source'],r['model_key'],r['color_key'],r['storage_gb'])
        old=db.execute('SELECT * FROM catalog_prices WHERE kind=? AND source=? AND model_key=? AND color_key=? AND storage_gb=?',key).fetchone()
        if old is None:
            db.execute('INSERT INTO catalog_prices(kind,source,model,model_key,color,color_key,storage_gb,approved,observed,observed_at,observed_snapshot,proposed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)', (kind,r['source'],r['model'],r['model_key'],r['color'],r['color_key'],r['storage_gb'],r['price_eur'] if initial else None,r['price_eur'],r['scanned_at'],r['sid'],None if initial else r['price_eur']))
            if not initial:
                db.execute("INSERT INTO catalog_events(price_id,value,status) VALUES(last_insert_rowid(),?,'pending')",(r['price_eur'],))
            continue
        if (r['scanned_at'],r['sid']) < (old['observed_at'] or '',old['observed_snapshot'] or 0): continue
        value=r['price_eur']
        if old['observed']==value:
            if (old['observed_at'],old['observed_snapshot']) != (r['scanned_at'],r['sid']):
                db.execute('UPDATE catalog_prices SET observed_at=?,observed_snapshot=? WHERE id=?',(r['scanned_at'],r['sid'],old['id']))
            continue
        db.execute("UPDATE catalog_events SET status='superseded', decided_at=CURRENT_TIMESTAMP WHERE price_id=? AND status='pending'",(old['id'],))
        if value==old['approved']:
            db.execute('UPDATE catalog_prices SET observed=?,observed_at=?,observed_snapshot=?,proposed=NULL,dismissed=NULL WHERE id=?',(value,r['scanned_at'],r['sid'],old['id']))
            continue
        auto=False
        if state['mode']=='auto' and old['approved'] and state['up_limit'] is not None and state['down_limit'] is not None:
            delta=(value-old['approved'])/old['approved']*100
            auto= -state['down_limit'] <= delta <= state['up_limit']
        db.execute('UPDATE catalog_prices SET observed=?,observed_at=?,observed_snapshot=?,proposed=?,approved=?,dismissed=NULL WHERE id=?',(value,r['scanned_at'],r['sid'],None if auto else value,value if auto else old['approved'],old['id']))
        db.execute('INSERT INTO catalog_events(price_id,value,status,actor,decided_at) VALUES(?,?,?,?,CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END)',(old['id'],value,'auto' if auto else 'pending','automatico' if auto else None,auto))
    if initial: db.execute('UPDATE catalog_state SET initialized=1 WHERE kind=?',(kind,))

def rules(db, kind, mode, up, down):
    if kind not in KINDS or mode not in ('manual','auto'): raise ValueError('regola non valida')
    if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=100) for v in (up,down)): raise ValueError('soglia non valida')
    if mode=='auto' and (up is None or down is None): raise ValueError('configurare entrambe le soglie')
    db.execute('UPDATE catalog_state SET mode=?,up_limit=?,down_limit=? WHERE kind=?',(mode,up,down,kind))

def manual_price(db, data, actor):
    kind=data.get('kind'); source=data.get('source'); model=data.get('model'); color=data.get('color'); capacity=data.get('storage_gb'); price=data.get('price')
    if kind not in KINDS or not all(isinstance(x,str) and 0<len(x.strip())<=120 for x in (source,model,color)) or type(capacity) is not int or not 0<capacity<=8192 or not _valid_price(price): raise ValueError('prezzo non valido')
    source='principale' if kind=='sale' else _key(source)
    db.execute('''INSERT INTO catalog_prices(kind,source,model,model_key,color,color_key,storage_gb,approved) VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(kind,source,model_key,color_key,storage_gb) DO UPDATE SET approved=excluded.approved,proposed=NULL,dismissed=NULL''',(kind,source,model.strip(),_key(model),color.strip(),_key(color),capacity,price))
    row=db.execute('SELECT id FROM catalog_prices WHERE kind=? AND source=? AND model_key=? AND color_key=? AND storage_gb=?',(kind,source,_key(model),_key(color),capacity)).fetchone()
    db.execute("UPDATE catalog_events SET status='superseded',decided_at=CURRENT_TIMESTAMP WHERE price_id=? AND status='pending'",(row['id'],))
    db.execute("INSERT INTO catalog_events(price_id,value,status,actor,decided_at) VALUES(?,?,'manual',?,CURRENT_TIMESTAMP)",(row['id'],price,actor))

def decide(db, ids, decision, actor):
    if decision not in ('approve','reject') or not isinstance(ids,list) or not ids or len(ids)>10000 or any(type(i) is not int for i in ids) or len(set(ids))!=len(ids): raise ValueError('selezione non valida')
    for event_id in ids:
        row=db.execute("SELECT e.*,p.proposed FROM catalog_events e JOIN catalog_prices p ON p.id=e.price_id WHERE e.id=? AND e.status='pending'",(event_id,)).fetchone()
        if not row or row['proposed']!=row['value']: raise ValueError('proposta non più disponibile')
    for event_id in ids:
        row=db.execute('SELECT * FROM catalog_events WHERE id=?',(event_id,)).fetchone()
        if decision=='approve': db.execute('UPDATE catalog_prices SET approved=?,proposed=NULL,dismissed=NULL WHERE id=?',(row['value'],row['price_id']))
        else: db.execute('UPDATE catalog_prices SET proposed=NULL,dismissed=? WHERE id=?',(row['value'],row['price_id']))
        db.execute('UPDATE catalog_events SET status=?,actor=?,decided_at=CURRENT_TIMESTAMP WHERE id=?',(decision,actor,event_id))

def list_catalog(db, kind):
    if kind not in KINDS: raise ValueError('listino non valido')
    reconcile(db,kind)
    return {'rules':dict(db.execute('SELECT kind,mode,up_limit,down_limit FROM catalog_state WHERE kind=?',(kind,)).fetchone()),
            'prices':[dict(r) for r in db.execute('''SELECT p.id,p.kind,p.source,p.model,p.color,p.storage_gb,p.approved,p.proposed,
                (SELECT id FROM catalog_events e WHERE e.price_id=p.id AND e.status='pending' ORDER BY id DESC LIMIT 1) AS event_id
                FROM catalog_prices p WHERE p.kind=? ORDER BY p.model,p.storage_gb,p.color,p.source''',(kind,))]}

def notifications(db, actor):
    return [dict(r) for r in db.execute('''SELECT e.id,e.status,p.kind,p.source,p.model,p.color,p.storage_gb,p.approved,e.value,
       EXISTS(SELECT 1 FROM catalog_notification_reads r WHERE r.event_id=e.id AND r.actor=?) AS is_read
       FROM catalog_events e JOIN catalog_prices p ON p.id=e.price_id WHERE e.status='pending' ORDER BY e.id DESC''',(actor,))]

def mark_read(db, actor, ids):
    if not isinstance(ids,list) or len(ids)>10000 or any(type(i) is not int for i in ids): raise ValueError('selezione non valida')
    for i in ids:
        if db.execute('SELECT 1 FROM catalog_events WHERE id=?',(i,)).fetchone():
            db.execute('INSERT OR IGNORE INTO catalog_notification_reads(event_id,actor) VALUES(?,?)',(i,actor))
