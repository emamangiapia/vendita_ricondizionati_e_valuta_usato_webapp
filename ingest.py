"""Entry point richiamabile dagli scraper senza dipendenze Streamlit."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from storage import import_xlsx, DATABASE_PATH

if os.name == 'nt':
    from dotenv import dotenv_values
    private_config = Path(os.environ.get('WEFIX_AGENT_ENV', r'C:\Users\emanu\apps\secrets\wefix-prices.env'))
    if private_config.is_file():
        values = dotenv_values(private_config)
        for key in ('WEFIX_DB_API_URL','WEFIX_DB_API_TOKEN'):
            if values.get(key): os.environ.setdefault(key, values[key])


def post_api(route, payload):
    endpoint = os.environ.get("WEFIX_DB_API_URL", "").rstrip("/")
    token = os.environ.get("WEFIX_DB_API_TOKEN", "")
    target = urlsplit(endpoint)
    if (target.scheme != "https" and not (target.scheme == "http" and target.hostname in {"127.0.0.1", "localhost", "::1"})) or not target.netloc:
        raise ValueError("L'API WeFix richiede HTTPS, salvo accesso locale")
    if not token:
        raise ValueError("WEFIX_DB_API_TOKEN non configurato")
    body = json.dumps(payload, default=str).encode("utf-8")
    request = Request(endpoint + route, data=body,
                      headers={"Authorization":"Bearer " + token,
                               "Content-Type":"application/json"}, method="POST")
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    with build_opener(NoRedirect).open(request, timeout=60) as response:
        return json.load(response)


def send_xlsx(path, kind, drive_url=""):
    """Invia il listino all'API configurata, preservando la modalita locale."""
    data = Path(path).read_bytes()
    if not data or len(data) > 16 * 1024 * 1024:
        raise ValueError("Dimensione del listino non valida")
    return post_api('/ingest', {"kind":kind, "filename":Path(path).name,
                       "content":base64.b64encode(data).decode("ascii"),
                       "drive_url":drive_url})

def main():
    parser=argparse.ArgumentParser(description="Importa un listino Excel nel DB WeFix locale")
    parser.add_argument("xlsx",type=Path)
    parser.add_argument("--kind",required=True,choices=["sale","tradein"])
    parser.add_argument("--drive-url",default="")
    parser.add_argument("--scanned-at",default=None)
    args=parser.parse_args()
    if not args.xlsx.is_file():
        parser.error(f"File Excel inesistente: {args.xlsx}")
    if os.environ.get("WEFIX_DB_API_URL"):
        result=send_xlsx(args.xlsx.resolve(), args.kind, args.drive_url)
        print(f"[WEFIX DB] {result['status']}: {result['count']} prezzi inviati all'API")
    else:
        result=import_xlsx(args.xlsx.resolve(),kind=args.kind,
                           scanned_at=args.scanned_at,source_url=args.drive_url)
        print(f"[WEFIX DB] {result['status']}: {result['count']} prezzi in {DATABASE_PATH}")

if __name__=="__main__":
    main()
