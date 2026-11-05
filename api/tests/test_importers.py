"""Comprueba lo que más fácil se rompe al importar. Se ejecuta con: python -m tests.test_importers"""
import maps_link
from importers.cne_pdf import cells_of, to_record
from importers.load_csv import validated
from importers.locate_roads import match_place


def base_row(**changes):
    row = {
        "province": "GUAYAS", "provider": "ACME", "code": "1", "kind": "FIJA", "height": "4",
        "width": "8", "address": "AV. X", "price": "1.116,50", "unit": "POR DÍA",
    }
    return {**row, **changes}


def main():
    # Celdas repetidas contiguas se quitan, pero un 4x4 en columnas separadas se conserva
    assert cells_of(["6018", "6018", None, "FIJA"]) == [(0, "6018"), (3, "FIJA")]
    assert cells_of(["4", None, "4"]) == [(0, "4"), (2, "4")]

    record = to_record(base_row())
    assert record["price_usd"] == "1116.50" and record["price_unit"] == "dia"
    assert record["lat"] == "" and record["location_precision"] == ""

    # Coordenadas partidas en dos líneas dentro de la dirección
    record = to_record(base_row(address="AV. DURAN - TAMBO / -2.189357, - 79.826095"))
    assert record["address"] == "AV. DURAN - TAMBO"
    assert (record["lat"], record["lng"]) == (-2.189357, -79.826095)
    assert record["location_precision"] == "exacta"

    assert to_record(base_row(kind="MÓVIL"))["type"] == "movil"
    assert to_record(base_row(address="AV. X, PUENTE PEATONAL ESPOCH"))["type"] == "puente"
    assert to_record(base_row(address="AV. X, INGRESO PEATONAL"))["type"] == "estatica"

    # Coordenadas al norte de la línea ecuatorial y en grados, minutos y segundos
    record = to_record(base_row(address="LA ESPERANZA / 0.305745, -78.229943"))
    assert (record["lat"], record["lng"]) == (0.305745, -78.229943)
    record = to_record(base_row(address="Babahoyo/Redondel/1°48'44.4\"S 79°30'30.0\"W"))
    assert record["address"] == "Babahoyo/Redondel"
    assert (record["lat"], record["lng"]) == (-1.812333, -79.508333)
    record = to_record(base_row(address="Calacali /Entrada/0°00'54.0\"N 78°28'46.5\"W"))
    assert (record["lat"], record["lng"]) == (0.015, -78.479583)

    # Gana la vía citada primero, y los lugares puntuales ganan a las vías
    assert match_place("AV. C. J. AROSEMENA HACIA VÍA DAULE", "GUAYAS") == "Avenida Carlos Julio Arosemena, Guayaquil"
    assert match_place("AV. ORRANTIA FRENTE A MALL DEL SOL", "GUAYAS") == "Mall del Sol, Guayaquil"
    # Nombre repetido en Cuenca: no se ubica en Guayaquil si la empresa no está en Guayas
    assert match_place("AV. DE LAS AMERICAS Y LUIS CORDERO", "AZUAY") is None
    assert match_place("AV. DE LAS AMERICAS Y CALLE 11", "GUAYAS") == "Avenida de las Américas, Guayaquil"

    assert match_place("AV. NICOLAS LAPENTI SECTOR INGRESO HACIA SAMBORONDON", "GUAYAS") == "Avenida Nicolás Lapentti, Durán"
    assert match_place("MANTA: AV. PUERTO AEROPUERTO A LADO DEL TERMINAL TERRESTRE", "MANABI") is None

    valid = {"source": "sv", "source_ref": "1", "provider_name": "A", "address": "B", "type": "estatica"}
    assert validated({**valid, "lat": "-2.1", "lng": "-79.9"})["location_precision"] == "exacta"
    assert validated(valid)["location_precision"] is None
    for bad in ({"type": "otra"}, {"lat": "-2.1"}, {"lat": "99", "lng": "0"}, {"price_usd": "caro"}, {"address": ""}):
        try:
            validated({**valid, **bad})
        except ValueError:
            continue
        raise AssertionError(f"debió rechazarse: {bad}")
    assert maps_link.coords_from_text("https://www.google.com/maps?q=-2.15,-79.9") == (-2.15, -79.9)
    assert not maps_link.is_allowed("https://evil.io/?google.com")
    print("ok")


if __name__ == "__main__":
    main()
