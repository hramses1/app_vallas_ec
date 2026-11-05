"""Convierte el tarifario de vallas del CNE (PDF público, 2023) al CSV común de importación.

Uso: python -m importers.cne_pdf ruta/Tarifario-Vallas.pdf ../data/cne_2023.csv
Fuente: https://www.cne.gob.ec/wp-content/uploads/2023/07/Tarifario-Vallas.pdf
"""
import csv
import re
import sys

import pdfplumber

from importers.csv_format import FIELDS

COORDS = re.compile(r"(-?\s*\d{1,2}[.,]\d{3,})\s*[,;/ ]\s*(-\s*\d{2}[.,]\d{3,})")
# Grados, minutos y segundos: 0°56'35.6"S 78°36'40.9"W (a veces sin la O/W final)
DMS = re.compile(
    r"(\d{1,2})\s*[°º]\s*(\d{1,2})\s*'\s*([\d.,]+)\s*\"?\s*([NS])\s*"
    r"(\d{2})\s*[°º]\s*(\d{1,2})\s*'\s*([\d.,]+)\s*\"?\s*[WO]?",
    re.I,
)
NOTE = "Tarifa electoral declarada ante el CNE en 2023; no es precio comercial vigente"
SKIP_ROW = re.compile(r"PROVINCIA|PRODUCTO|METROS")


def clean(cell):
    return re.sub(r"\s+", " ", cell or "").strip()


def cells_of(raw):
    """Celdas no vacías como (posición, texto). El PDF repite celdas contiguas en algunas filas."""
    cells = []
    for i, cell in enumerate(raw):
        text = clean(cell)
        if text and not (cells and cells[-1] == (i - 1, text)):
            cells.append((i, text))
    return cells


def parse_rows(pdf_path):
    """Una valla por fila. Las columnas se desplazan entre páginas, así que se usa el orden de las
    celdas, y el texto que el PDF parte en varias filas se une a la valla anterior."""
    current = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for raw in table:
                    cells = cells_of(raw)
                    # Las tablas de una columna son repeticiones sueltas del nombre de la empresa
                    if len(raw) == 1 or not cells or SKIP_ROW.search(cells[0][1]):
                        continue
                    if len(cells) >= 8 and cells[2][1].isdigit():
                        if current:
                            yield current
                        texts = [text for _, text in cells]
                        current = {
                            "province": texts[0],
                            "provider": texts[1],
                            "code": texts[2],
                            "kind": texts[3],
                            "height": texts[4],
                            "width": texts[5],
                            "address": " ".join(texts[6:-2]),
                            "price": texts[-2],
                            "unit": texts[-1],
                            "kind_pos": cells[3][0],
                            "unit_pos": cells[-1][0],
                        }
                    elif current:
                        for pos, text in cells:
                            if pos == 0:
                                key = "province"
                            elif pos < current["kind_pos"]:
                                key = "provider"
                            elif pos == current["unit_pos"]:
                                key = "unit"
                            else:
                                key = "address"
                            current[key] = f"{current[key]} {text}".strip()
    if current:
        yield current


def billboard_type(row):
    if "MÓVIL" in row["kind"].upper() or "MOVIL" in row["kind"].upper():
        return "movil"
    if re.search(r"\bLED\b|PANTALLA", row["address"], re.I):
        return "digital"
    # "Ingreso peatonal" no es un puente
    if re.search(r"(PUENTE|PASO) PEATONAL", row["address"], re.I):
        return "puente"
    return "estatica"


def find_coords(address):
    """Devuelve (lat, lng, posición donde empiezan) o None. Ecuador siempre está al oeste."""
    match = DMS.search(address)
    if match:
        d1, m1, s1, hemisphere, d2, m2, s2 = match.groups()
        lat = int(d1) + int(m1) / 60 + float(s1.replace(",", ".")) / 3600
        lng = int(d2) + int(m2) / 60 + float(s2.replace(",", ".")) / 3600
        return round(lat if hemisphere.upper() == "N" else -lat, 6), round(-lng, 6), match.start()
    match = COORDS.search(address)
    if match:
        lat, lng = (float(g.replace(" ", "").replace(",", ".")) for g in match.groups())
        return lat, lng, match.start()
    return None


def to_record(row):
    lat = lng = ""
    address = row["address"]
    found = find_coords(address)
    if found:
        lat, lng, start = found
        address = address[:start].rstrip(" /")
    return {
        "source": "cne_2023",
        "source_ref": f"{row['provider']}:{row['code']}",
        "provider_name": row["provider"],
        "province": row["province"],
        "type": billboard_type(row),
        "address": address,
        "height_m": row["height"].replace(",", "."),
        "width_m": row["width"].replace(",", "."),
        "price_usd": row["price"].replace(".", "").replace(",", "."),
        "price_unit": row["unit"].upper().replace("POR", "").strip().lower().replace("í", "i"),
        "lat": lat,
        "lng": lng,
        "location_precision": "exacta" if found else "",
        "contact_email": "",
        "contact_phone": "",
        "notes": NOTE,
    }


def main(pdf_path, out_path):
    records = {}
    for row in parse_rows(pdf_path):
        record = to_record(row)
        records[record["source_ref"]] = record
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(records.values())
    print(f"{len(records)} vallas -> {out_path}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
