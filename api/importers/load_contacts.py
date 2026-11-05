"""Carga los contactos que publica cada empresa. Se puede repetir: actualiza por empresa.

Uso: python -m importers.load_contacts /data/contactos_empresas.csv
"""
import csv
import os
import sys

import psycopg

UPSERT = """
INSERT INTO provider_contacts (provider_name, website, phone, email, address, source_url)
VALUES (%(provider_name)s, %(website)s, %(phone)s, %(email)s, %(address)s, %(source_url)s)
ON CONFLICT (provider_name) DO UPDATE SET
    website = EXCLUDED.website, phone = EXCLUDED.phone, email = EXCLUDED.email,
    address = EXCLUDED.address, source_url = EXCLUDED.source_url
"""


def main(path):
    with open(path, newline="", encoding="utf-8-sig") as f, psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        rows = [{key: value.strip() or None for key, value in row.items()} for row in csv.DictReader(f)]
        for row in rows:
            conn.execute(UPSERT, row)
    print(f"{len(rows)} empresas cargadas")


if __name__ == "__main__":
    main(sys.argv[1])
