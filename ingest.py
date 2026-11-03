"""Entry point richiamabile dagli scraper senza dipendenze Streamlit."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from storage import import_xlsx, DATABASE_PATH

def main():
    parser=argparse.ArgumentParser(description="Importa un listino Excel nel DB WeFix locale")
    parser.add_argument("xlsx",type=Path)
    parser.add_argument("--kind",required=True,choices=["sale","tradein"])
    parser.add_argument("--drive-url",default="")
    parser.add_argument("--scanned-at",default=None)
    args=parser.parse_args()
    if not args.xlsx.is_file():
        parser.error(f"File Excel inesistente: {args.xlsx}")
    result=import_xlsx(args.xlsx.resolve(),kind=args.kind,
                       scanned_at=args.scanned_at,source_url=args.drive_url)
    print(f"[WEFIX DB] {result['status']}: {result['count']} prezzi in {DATABASE_PATH}")

if __name__=="__main__":
    main()
