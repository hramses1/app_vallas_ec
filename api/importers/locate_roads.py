"""Da ubicación aproximada a vallas de la zona piloto según la vía o el lugar que cita su dirección.

El punto es un punto de esa vía o lugar según OpenStreetMap, no la valla: puede estar a kilómetros
de ella. Sirve para el mapa mientras no se releve la coordenada exacta. Reescribe el CSV; las
ubicaciones exactas no se tocan. data/lugares_osm.json guarda los puntos y admite correcciones a mano.

Uso: python -m importers.locate_roads ../data/cne_2023.csv
Geocodificador: Nominatim (OpenStreetMap, licencia ODbL), máximo una consulta por segundo.
"""
import csv
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from importers.csv_format import FIELDS

VIEWBOX = "-80.02,-1.98,-79.78,-2.32"  # Guayaquil, Samborondón y Durán: oeste, norte, este, sur
CACHE = Path(__file__).resolve().parents[2] / "data" / "lugares_osm.json"

# Lugares puntuales: se prefieren a la vía porque quedan más cerca de la valla.
# Solo nombres únicos en la zona: "Terminal Terrestre", por ejemplo, hay en cada ciudad.
LANDMARKS = {
    r"MALL DEL SOL": "Mall del Sol, Guayaquil",
    r"LAPENT+I.*TERM": "Terminal Terrestre de Durán",
    r"SAN MARINO": "San Marino Shopping, Guayaquil",
    r"POLICENTRO": "Policentro, Guayaquil",
    r"PARQUE SAMANES": "Parque Samanes, Guayaquil",
    r"AVENTURA PLAZA": "Aventura Plaza, Guayaquil",
    r"U\. CAT[OÓ]LICA": "Universidad Católica de Santiago de Guayaquil",
}
# Vías cuyo nombre solo existe en la zona piloto
ROADS = {
    r"JUAN TANCA": "Avenida Juan Tanca Marengo, Guayaquil",
    r"MEN[EÉ]NDEZ GILBERT": "Avenida Pedro Menéndez Gilbert, Guayaquil",
    r"C\. ?J\. ?(A\.|AROSEMENA)|CARLOS JULIO AROSEMENA": "Avenida Carlos Julio Arosemena, Guayaquil",
    r"ORRANTIA": "Avenida Joaquín Orrantia, Guayaquil",
    r"PLAZA DA[NÑ]IN": "Avenida Plaza Dañín, Guayaquil",
    r"SAMBOROND[OÓ]N": "Avenida Samborondón",
    r"PERIMETRAL": "Avenida Perimetral, Guayaquil",
    r"V[IÍ]A (A )?DAULE": "Vía a Daule, Guayaquil",
    r"DEL BOMBERO": "Avenida del Bombero, Guayaquil",
    r"DUR[AÁ]N ?-? ?(TAMBO|BOLICHE)|V[IÍ]A DUR[AÁ]N": "Vía Durán Tambo, Durán",
    r"LAPENT+I": "Avenida Nicolás Lapentti, Durán",
    r"DUR[AÁ]N.*YAGUACHI": "Durán Yaguachi, Durán",
}
# Nombres repetidos en otras ciudades: solo cuentan si la empresa las declaró en Guayas
GUAYAS_ROADS = {
    r"DE LAS AM[EÉ]RICAS": "Avenida de las Américas, Guayaquil",
    r"FRANCISCO DE ORELLANA": "Avenida Francisco de Orellana, Guayaquil",
    r"LAS MONJAS": "Avenida Las Monjas, Guayaquil",
}


def match_place(address, province):
    """Nombre a geocodificar para esta dirección, o None. Gana la vía que se cita primero."""
    for pattern, place in LANDMARKS.items():
        if re.search(pattern, address, re.I):
            return place
    roads = {**ROADS, **GUAYAS_ROADS} if province == "GUAYAS" else ROADS
    found = [(m.start(), place) for pattern, place in roads.items() if (m := re.search(pattern, address, re.I))]
    return min(found)[1] if found else None


def geocode(place):
    query = urllib.parse.urlencode(
        {"q": place + ", Ecuador", "format": "json", "limit": 1, "viewbox": VIEWBOX, "bounded": 1}
    )
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{query}",
        headers={"User-Agent": "proyecto-vallas-prototipo"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        results = json.load(response)
    time.sleep(1.1)
    return (results[0]["lat"], results[0]["lon"]) if results else None


def main(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    located = 0
    for row in rows:
        if row["location_precision"] == "exacta":
            continue
        place = match_place(row["address"], row["province"])
        if not place:
            continue
        if place not in cache:
            cache[place] = geocode(place)
            print(place, "->", cache[place])
        if cache[place]:
            row["lat"], row["lng"] = cache[place]
            row["location_precision"] = "aproximada"
            located += 1
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{located} vallas con ubicación aproximada")


if __name__ == "__main__":
    main(sys.argv[1])
