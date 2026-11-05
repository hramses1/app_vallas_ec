"""Carga un CSV en formato común a la base. Se puede repetir: actualiza por (source, source_ref).

Uso: python -m importers.load_csv /data/cne_2023.csv
Una celda vacía nunca borra lo que ya hay, y una ubicación exacta nunca se pisa con una aproximada.
"""
import csv
import os
import sys

import psycopg

from importers.csv_format import FIELDS

TYPES = {"estatica", "digital", "mupi", "puente", "movil"}
UNITS = {"hora", "dia", "mes", ""}

UPSERT = """
INSERT INTO billboards (source, source_ref, provider_name, province, type, address, height_m, width_m,
                        price_usd, price_unit, location, location_precision,
                        contact_email, contact_phone, notes)
VALUES (%(source)s, %(source_ref)s, %(provider_name)s, %(province)s, %(type)s, %(address)s,
        %(height_m)s, %(width_m)s, %(price_usd)s, %(price_unit)s,
        CASE WHEN %(lat)s::float8 IS NOT NULL
             THEN ST_SetSRID(ST_MakePoint(%(lng)s::float8, %(lat)s::float8), 4326) END,
        %(location_precision)s, %(contact_email)s, %(contact_phone)s, %(notes)s)
ON CONFLICT (source, source_ref) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    province = COALESCE(EXCLUDED.province, billboards.province),
    type = EXCLUDED.type,
    address = EXCLUDED.address,
    height_m = COALESCE(EXCLUDED.height_m, billboards.height_m),
    width_m = COALESCE(EXCLUDED.width_m, billboards.width_m),
    price_usd = COALESCE(EXCLUDED.price_usd, billboards.price_usd),
    price_unit = COALESCE(EXCLUDED.price_unit, billboards.price_unit),
    location = CASE WHEN EXCLUDED.location IS NULL
                      OR (billboards.location_precision = 'exacta'
                          AND EXCLUDED.location_precision <> 'exacta')
                    THEN billboards.location ELSE EXCLUDED.location END,
    location_precision = CASE WHEN EXCLUDED.location IS NULL
                                OR (billboards.location_precision = 'exacta'
                                    AND EXCLUDED.location_precision <> 'exacta')
                              THEN billboards.location_precision ELSE EXCLUDED.location_precision END,
    contact_email = COALESCE(EXCLUDED.contact_email, billboards.contact_email),
    contact_phone = COALESCE(EXCLUDED.contact_phone, billboards.contact_phone),
    notes = COALESCE(EXCLUDED.notes, billboards.notes),
    updated_at = now()
"""


def validated(row):
    """Devuelve la fila lista para insertar; lanza ValueError con el motivo si no sirve."""
    row = {key: (row.get(key) or "").strip() or None for key in FIELDS}
    for key in ("source", "source_ref", "provider_name", "address"):
        if not row[key]:
            raise ValueError(f"falta {key}")
    if row["type"] not in TYPES:
        raise ValueError(f"tipo desconocido: {row['type']}")
    if (row["price_unit"] or "") not in UNITS:
        raise ValueError(f"unidad de precio desconocida: {row['price_unit']}")
    if bool(row["lat"]) != bool(row["lng"]):
        raise ValueError("lat y lng van juntas")
    if row["lat"]:
        lat, lng = float(row["lat"]), float(row["lng"])
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError(f"coordenadas fuera de rango: {lat}, {lng}")
        # Quien llena coordenadas a mano las leyó de la valla: sin precisión indicada, son exactas
        row["location_precision"] = row["location_precision"] or "exacta"
    else:
        row["location_precision"] = None
    for key in ("height_m", "width_m", "price_usd"):
        if row[key]:
            float(row[key])
    return row


def main(path):
    loaded, skipped = 0, 0
    with open(path, newline="", encoding="utf-8-sig") as f, psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        # start=2: la línea 1 del archivo es el encabezado
        for line, raw in enumerate(csv.DictReader(f), start=2):
            try:
                conn.execute(UPSERT, validated(raw))
                loaded += 1
            except ValueError as error:
                skipped += 1
                print(f"línea {line} omitida: {error}")
    print(f"{loaded} vallas cargadas, {skipped} omitidas")


if __name__ == "__main__":
    main(sys.argv[1])
