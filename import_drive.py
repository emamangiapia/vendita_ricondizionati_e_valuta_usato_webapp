"""Importa tutti i listini storici delle due cartelle Google Drive in SQLite.

Nessun token, file XLSX o dato economico viene scritto nel repository.
"""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import sys

from storage import connection, import_rows, init_db, parse_scanned_at

DRIVE_ROOTS = {
    "sale": "1jexJNN-jIRLlvpBTziZpZl8bsxf4kuGf",
    "tradein": "1Nf6CCKSisap6NXv9Fs0T0iSrBVplua8C",
}
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def credentials_path():
    value = os.getenv("WEFIX_GOOGLE_CREDENTIALS") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    base = Path(__file__).resolve().parent.parent
    candidates = [
        Path(value).expanduser() if value else None,
        base / "valuta_usato_platform" / "constants" / "valutausato-f3fbfb65ccc3.json",
        base / "valutaUsato_platform" / "constants" / "valutausato-f3fbfb65ccc3.json",
        base / "calcola_acquista_usato" / "calcola_acquista_usato" / "valutausato-f3fbfb65ccc3.json",
    ]
    return next((str(p) for p in candidates if p and p.is_file()), None)

def build_services():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    filename = credentials_path()
    if not filename:
        raise FileNotFoundError(
            "Credenziali Drive assenti. Imposta WEFIX_GOOGLE_CREDENTIALS "
            "con il percorso del service account abilitato per entrambe le cartelle."
        )
    creds = Credentials.from_service_account_file(filename, scopes=[
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ])
    return (build("drive", "v3", credentials=creds, cache_discovery=False),
            build("sheets", "v4", credentials=creds, cache_discovery=False))

def list_children(drive, parent_id):
    token = None
    while True:
        response = drive.files().list(
            q=f"'{parent_id}' in parents and trashed=false",
            fields="nextPageToken,files(id,name,mimeType,createdTime,webViewLink,parents)",
            pageSize=1000, pageToken=token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute(num_retries=8)
        yield from response.get("files", [])
        token = response.get("nextPageToken")
        if not token:
            break

def choose_file(files, kind):
    valid = [f for f in files if f.get("mimeType") in {SHEET_MIME, XLSX_MIME}]
    if not valid:
        return None
    def priority(f):
        name = f["name"].casefold()
        native = f["mimeType"] == SHEET_MIME
        if native and name.startswith("be_"): return 0
        if native and "sortedroundup" in name: return 1
        if native and ("sorted" in name or "prezzi" in name): return 2
        if native: return 3
        if f["mimeType"] == XLSX_MIME and "sortedroundup" in name: return 4
        return 5
    return sorted(valid, key=lambda f: (priority(f), f["name"]))[0]

def native_sheet(drive_sheets, file_id):
    result = drive_sheets.spreadsheets().get(
        spreadsheetId=file_id, fields="sheets(properties(title))"
    ).execute(num_retries=8)
    tabs = [x["properties"]["title"] for x in result.get("sheets", [])]
    if not tabs:
        raise ValueError("Google Sheet senza fogli")
    ordered = sorted(tabs, key=lambda x: (x.casefold() != "apple", x))
    for tab in ordered:
        safe = tab.replace("'", "''")
        result = drive_sheets.spreadsheets().values().get(
            spreadsheetId=file_id,
            range=f"'{safe}'!A1:AZ5000",
            valueRenderOption="UNFORMATTED_VALUE",
        ).execute(num_retries=8)
        rows = result.get("values", [])
        if rows:
            yield tab, rows

def xlsx_sheet(drive, file_id):
    from googleapiclient.http import MediaIoBaseDownload
    from openpyxl import load_workbook
    buf = io.BytesIO()
    request = drive.files().get_media(fileId=file_id)
    downloader = MediaIoBaseDownload(buf, request)
    finished = False
    while not finished:
        _, finished = downloader.next_chunk(num_retries=8)
    buf.seek(0)
    wb = load_workbook(buf, read_only=True, data_only=True)
    try:
        tabs = sorted(wb.sheetnames, key=lambda x: (x.casefold() != "apple", x))
        for tab in tabs:
            yield tab, list(wb[tab].values)
    finally:
        wb.close()

def seen(kind, file_id):
    with connection() as db:
        return db.execute("""SELECT 1 FROM snapshots
           WHERE kind=? AND source_id=? AND record_count>0 LIMIT 1""", (kind,file_id)).fetchone() is not None

def run(kind=None, limit=0):
    remote = bool(os.environ.get('WEFIX_DB_API_URL'))
    if not remote:
        init_db()
    drive, sheets = build_services()
    stats = {"folders":0,"imported":0,"skipped":0,"failed":0,"prices":0}
    kinds = [kind] if kind else list(DRIVE_ROOTS)
    for category in kinds:
        root = DRIVE_ROOTS[category]
        print(f"\n[DRIVE] Inizio importazione {category} | folder={root}", flush=True)
        entries = list(list_children(drive, root))
        folders = [x for x in entries if x.get("mimeType") == "application/vnd.google-apps.folder"]
        files_at_root = [x for x in entries if x.get("mimeType") != "application/vnd.google-apps.folder"]
        groups = [(f["name"], list(list_children(drive, f["id"]))) for f in folders]
        if files_at_root:
            groups.append(("root", files_at_root))
        groups.sort(key=lambda t: t[0], reverse=True)
        for folder_name, children in groups:
            if limit and stats["folders"] >= limit:
                break
            stats["folders"] += 1
            selected = choose_file(children, category)
            if not selected:
                continue
            file_id = selected["id"]
            filename = selected["name"]
            run_at = parse_scanned_at(folder_name if folder_name != "root" else filename,
                                       fallback=selected.get("createdTime"))
            source_url = selected.get("webViewLink") or (
                f"https://drive.google.com/file/d/{file_id}/view"
            )
            try:
                tabs = (native_sheet(sheets, file_id) if selected["mimeType"] == SHEET_MIME
                        else xlsx_sheet(drive, file_id))
                imported = False
                last_error = None
                for tab, rows in tabs:
                    try:
                        payload = dict(rows=rows, kind=category,
                            source_id=file_id, filename=filename,
                            sheet_name=tab, scanned_at=run_at,
                            folder_name=folder_name, source_url=source_url,
                            is_primary=(tab.casefold()=="apple" or not imported))
                        if remote:
                            from ingest import post_api
                            result = post_api('/ingest-rows', payload)
                        else:
                            result = import_rows(**payload)
                        imported = True
                        stats["prices"] += result["count"]
                        stats[result["status"]] += 1
                        print(f"[OK] {category} | {folder_name} | {tab} | {result['count']} prezzi ({result['status']})",flush=True)
                    except ValueError as err:
                        last_error = str(err)
                if not imported:
                    raise ValueError(last_error or "Nessun foglio con intestazione prezzi valida")
            except Exception as exc:
                stats["failed"] += 1
                print(f"[WARN] {category} | {filename}: {exc}",flush=True)
    print(f"\n[RIEPILOGO] {stats}",flush=True)
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import storico prezzi da Drive")
    parser.add_argument("--kind", choices=["sale","tradein"])
    parser.add_argument("--limit", type=int, default=0,
                        help="Numero massimo di cartelle per test (0=senza limite)")
    args = parser.parse_args()
    run(kind=args.kind, limit=args.limit)
