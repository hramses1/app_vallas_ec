import csv
import io
import json
import os
import secrets
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

import maps_link
from importers.csv_format import FIELDS

app = FastAPI(title="Marketplace de vallas", version="0.1.0")

BillboardType = Literal["estatica", "digital", "mupi", "puente", "movil"]

PROPERTIES = """
    b.id::text, b.source, b.source_ref, b.provider_name, b.province, b.type, b.address,
    b.height_m::float8, b.width_m::float8, b.price_usd::float8, b.price_unit,
    b.location_precision, b.notes, b.verified_at,
    COALESCE(b.contact_phone, c.phone) AS contact_phone,
    COALESCE(b.contact_email, c.email) AS contact_email,
    c.website AS provider_website, c.address AS provider_address,
    ST_X(b.location) AS lng, ST_Y(b.location) AS lat
"""
FROM_BILLBOARDS = "FROM billboards b LEFT JOIN provider_contacts c USING (provider_name)"


# Una conexión por petición: basta para el prototipo. Usar psycopg_pool cuando haya tráfico real
def connect():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def to_feature(row):
    lng, lat = row.pop("lng"), row.pop("lat")
    geometry = {"type": "Point", "coordinates": [lng, lat]} if lat is not None else None
    return {"type": "Feature", "geometry": geometry, "properties": row}


@app.get("/api/billboards")
def list_billboards(
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lng: float | None = None,
    max_lng: float | None = None,
    type: Annotated[list[BillboardType] | None, Query()] = None,
    min_price: float | None = None,
    max_price: float | None = None,
    located: Annotated[bool, Query(description="false: vallas que aún no tienen punto en el mapa")] = True,
    provider: str | None = None,
    precision: Literal["exacta", "aproximada"] | None = None,
    q: Annotated[str | None, Query(description="Palabras a buscar en la dirección o la empresa")] = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 2000,
):
    """Vallas ubicadas, en GeoJSON. Pasa el recuadro visible del mapa para traer solo esas."""
    bbox = [min_lng, min_lat, max_lng, max_lat]
    if any(v is not None for v in bbox) and any(v is None for v in bbox):
        raise HTTPException(422, "El recuadro necesita min_lat, max_lat, min_lng y max_lng")

    where, params = ["b.location IS NOT NULL" if located else "b.location IS NULL", "b.removed_at IS NULL"], {"limit": limit}
    if bbox[0] is not None:
        where.append("b.location && ST_MakeEnvelope(%(w)s, %(s)s, %(e)s, %(n)s, 4326)")
        params.update(w=min_lng, s=min_lat, e=max_lng, n=max_lat)
    if type:
        where.append("b.type = ANY(%(types)s)")
        params["types"] = type
    # Las tarifas solo se comparan por día: un precio mensual no es comparable con uno diario
    if min_price is not None or max_price is not None:
        where.append("b.price_unit = 'dia'")
    if min_price is not None:
        where.append("b.price_usd >= %(min_price)s")
        params["min_price"] = min_price
    if max_price is not None:
        where.append("b.price_usd <= %(max_price)s")
        params["max_price"] = max_price
    if provider:
        where.append("b.provider_name ILIKE %(provider)s")
        params["provider"] = f"%{provider}%"
    if precision:
        where.append("b.location_precision = %(precision)s")
        params["precision"] = precision
    # Cada palabra debe aparecer en la dirección o la empresa; tildes y mayúsculas no importan
    for index, word in enumerate((q or "").split()[:8]):
        where.append(f"unaccent(b.address || ' ' || b.provider_name) ILIKE unaccent(%(q{index})s)")
        params[f"q{index}"] = f"%{word}%"

    sql = f"""
        SELECT {PROPERTIES} {FROM_BILLBOARDS}
        WHERE {' AND '.join(where)}
        ORDER BY b.id LIMIT %(limit)s
    """
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return {"type": "FeatureCollection", "features": [to_feature(row) for row in rows]}


@app.get("/api/billboards/pending.csv")
def export_pending(province: str | None = None, provider: str | None = None):
    """Vallas sin coordenada exacta, listas para llenar lat/lng y reimportar con load_csv."""
    where, params = ["(location_precision IS DISTINCT FROM 'exacta')", "removed_at IS NULL"], {}
    if province:
        where.append("province = %(province)s")
        params["province"] = province
    if provider:
        where.append("provider_name ILIKE %(provider)s")
        params["provider"] = f"%{provider}%"
    columns = [f for f in FIELDS if f not in ("lat", "lng", "location_precision")]
    sql = f"""
        SELECT {', '.join(columns)}, location_precision AS ubicacion_actual
        FROM billboards WHERE {' AND '.join(where)} ORDER BY provider_name, address
    """
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out = io.StringIO()
    writer = csv.DictWriter(out, FIELDS + ["ubicacion_actual"], restval="")
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="vallas_pendientes.csv"'},
    )


@app.get("/api/billboards/to-locate")
def to_locate(limit: Annotated[int, Query(ge=1, le=5000)] = 2000):
    """Lista de trabajo de la zona piloto: primero las que ya tienen una zona aproximada."""
    # La provincia del CNE deja entrar vallas de otras ciudades: se saltan a mano en /ubicar
    sql = f"""
        SELECT {PROPERTIES} {FROM_BILLBOARDS}
        WHERE b.removed_at IS NULL AND b.location_precision IS DISTINCT FROM 'exacta'
          AND (b.location IS NOT NULL OR b.province = 'GUAYAS')
        ORDER BY b.location IS NULL, b.provider_name, b.address
        LIMIT %s
    """
    with connect() as conn:
        return conn.execute(sql, (limit,)).fetchall()


@app.get("/api/billboards/{billboard_id}")
def get_billboard(billboard_id: UUID):
    sql = f"SELECT {PROPERTIES} {FROM_BILLBOARDS} WHERE b.id = %s"
    with connect() as conn:
        row = conn.execute(sql, (billboard_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Valla no encontrada")
    return to_feature(row)


def require_admin(x_admin_token: Annotated[str, Header()] = ""):
    if not secrets.compare_digest(x_admin_token.encode(), os.environ["ADMIN_TOKEN"].encode()):
        raise HTTPException(401, "Clave de administración incorrecta")


class Location(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


def update_billboard(billboard_id, sql, params=()):
    with connect() as conn:
        updated = conn.execute(sql, (*params, billboard_id)).rowcount
    if not updated:
        raise HTTPException(404, "Valla no encontrada")


@app.put("/api/billboards/{billboard_id}/location", status_code=204, dependencies=[Depends(require_admin)])
def set_location(billboard_id: UUID, location: Location):
    """Ubicación comprobada por una persona: queda exacta y verificada."""
    sql = """
        UPDATE billboards SET location = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
            location_precision = 'exacta', verified_at = now(), removed_at = NULL, updated_at = now()
        WHERE id = %s
    """
    update_billboard(billboard_id, sql, (location.lng, location.lat))


@app.post("/api/billboards/{billboard_id}/not-found", status_code=204, dependencies=[Depends(require_admin)])
def mark_not_found(billboard_id: UUID):
    sql = "UPDATE billboards SET removed_at = now(), updated_at = now() WHERE id = %s"
    update_billboard(billboard_id, sql)


@app.get("/ubicar", include_in_schema=False)
def locator_page():
    return FileResponse(Path(__file__).parent / "static" / "ubicar.html")


# Ecuador continental y Galápagos
class ReportIn(BaseModel):
    lat: float = Field(ge=-5.1, le=1.7)
    lng: float = Field(ge=-92.1, le=-75.1)
    address: str | None = Field(default=None, max_length=300)
    provider_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    price_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    price_unit: Literal["dia", "mes"] = "mes"
    type: BillboardType = "estatica"
    comment: str | None = Field(default=None, max_length=1000)
    website: str = ""  # trampa para bots: el formulario lo oculta a las personas


# Tope global contra abuso. Limitar por IP cuando la API esté detrás de un proxy real
REPORTS_PER_HOUR = 100


@app.post("/api/reports", status_code=201)
def create_report(report: ReportIn):
    """Recibe el reporte de un usuario. No se publica hasta que alguien lo aprueba."""
    if report.website:
        return {"status": "recibido"}  # al bot se le responde igual, pero no se guarda
    with connect() as conn:
        recent = conn.execute(
            "SELECT count(*) AS total FROM billboard_reports WHERE created_at > now() - interval '1 hour'"
        ).fetchone()
        if recent["total"] >= REPORTS_PER_HOUR:
            raise HTTPException(429, "Demasiados reportes en este momento")
        conn.execute(
            """
            INSERT INTO billboard_reports
                (location, address, provider_name, contact_phone, price_usd, price_unit, type, comment)
            VALUES (ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                report.lng,
                report.lat,
                (report.address or "").strip() or None,
                (report.provider_name or "").strip() or None,
                (report.contact_phone or "").strip() or None,
                report.price_usd,
                report.price_unit if report.price_usd is not None else None,
                report.type,
                (report.comment or "").strip() or None,
            ),
        )
    return {"status": "recibido"}


@app.get("/api/reports", dependencies=[Depends(require_admin)])
def list_reports():
    sql = """
        SELECT id::text, address, provider_name, contact_phone, price_usd::float8, price_unit,
               width_m::float8, height_m::float8, type, comment, created_at,
               ST_Y(location) AS lat, ST_X(location) AS lng
        FROM billboard_reports WHERE status = 'pendiente' ORDER BY created_at
    """
    with connect() as conn:
        return conn.execute(sql).fetchall()


def address_for_point(lat, lng):
    """Dirección legible del punto según OpenStreetMap; si falla, las coordenadas."""
    query = urllib.parse.urlencode({"lat": lat, "lon": lng, "format": "json", "zoom": 17})
    request = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/reverse?{query}",
        headers={"User-Agent": "proyecto-vallas-prototipo"},
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            name = json.load(response).get("display_name", "")
    except (OSError, ValueError):
        name = ""
    # Quita el código postal y el país, que no ayudan a ubicarse
    parts = [part.strip() for part in name.split(",") if part.strip() not in ("Ecuador",) and not part.strip().isdigit()]
    return ", ".join(parts) or f"Punto en el mapa: {lat:.6f}, {lng:.6f}"


@app.post("/api/reports/{report_id}/approve", status_code=204, dependencies=[Depends(require_admin)])
def approve_report(report_id: UUID):
    """Publica el reporte como aproximado: un clic en el mapa no es una ubicación confirmada.
    Pasa a exacta cuando se confirma en /ubicar."""
    # La dirección se busca aquí y no al reportar: así el público no genera consultas a Nominatim
    pending_sql = """
        SELECT address, ST_Y(location) AS lat, ST_X(location) AS lng
        FROM billboard_reports WHERE id = %s AND status = 'pendiente'
    """
    with connect() as conn:
        report = conn.execute(pending_sql, (report_id,)).fetchone()
    if not report:
        raise HTTPException(404, "Reporte pendiente no encontrado")
    address = report["address"] or address_for_point(report["lat"], report["lng"])

    sql = """
        WITH report AS (
            SELECT * FROM billboard_reports WHERE id = %(id)s AND status = 'pendiente' FOR UPDATE
        ), created AS (
            INSERT INTO billboards (source, source_ref, provider_name, type, address, location,
                                    location_precision, contact_phone, price_usd, price_unit,
                                    width_m, height_m, notes)
            SELECT 'reporte', id::text, COALESCE(provider_name, 'Empresa por identificar'), type, %(address)s,
                   location, 'aproximada', contact_phone, price_usd, price_unit, width_m, height_m,
                   'Reportada por un usuario. Datos sin confirmar'
            FROM report
            RETURNING id
        )
        UPDATE billboard_reports SET status = 'aprobado', billboard_id = (SELECT id FROM created)
        WHERE id = (SELECT id FROM report)
    """
    with connect() as conn:
        if not conn.execute(sql, {"id": report_id, "address": address}).rowcount:
            raise HTTPException(404, "Reporte pendiente no encontrado")


@app.post("/api/reports/{report_id}/reject", status_code=204, dependencies=[Depends(require_admin)])
def reject_report(report_id: UUID):
    sql = "UPDATE billboard_reports SET status = 'rechazado' WHERE id = %s AND status = 'pendiente'"
    with connect() as conn:
        if not conn.execute(sql, (report_id,)).rowcount:
            raise HTTPException(404, "Reporte pendiente no encontrado")


class BillboardEdit(BaseModel):
    address: str | None = Field(default=None, max_length=300)
    provider_name: str | None = Field(default=None, max_length=200)
    contact_phone: str | None = Field(default=None, max_length=30)
    price_usd: float | None = Field(default=None, ge=0, le=1_000_000)
    price_unit: Literal["dia", "mes"] = "mes"
    type: BillboardType = "estatica"
    width_m: float | None = Field(default=None, gt=0, le=200)
    height_m: float | None = Field(default=None, gt=0, le=200)

    def values(self):
        """Valores listos para guardar: lo que llega vacío queda sin dato."""
        data = self.model_dump()
        for key in ("address", "provider_name", "contact_phone"):
            data[key] = (data[key] or "").strip() or None
        if data["price_usd"] is None:
            data["price_unit"] = None
        return data


class ReportEdit(BillboardEdit):
    comment: str | None = Field(default=None, max_length=1000)


@app.put("/api/reports/{report_id}", status_code=204, dependencies=[Depends(require_admin)])
def edit_report(report_id: UUID, edit: ReportEdit):
    sql = """
        UPDATE billboard_reports SET address = %(address)s, provider_name = %(provider_name)s,
            contact_phone = %(contact_phone)s, price_usd = %(price_usd)s, price_unit = %(price_unit)s,
            type = %(type)s, width_m = %(width_m)s, height_m = %(height_m)s, comment = %(comment)s
        WHERE id = %(id)s AND status = 'pendiente'
    """
    values = edit.values()
    values["comment"] = (values["comment"] or "").strip() or None
    with connect() as conn:
        if not conn.execute(sql, {**values, "id": report_id}).rowcount:
            raise HTTPException(404, "Reporte pendiente no encontrado")


@app.get("/api/reports/published", dependencies=[Depends(require_admin)])
def list_published_reports(removed: bool = False):
    """Vallas nacidas de reportes. Con removed=true, las que se quitaron del mapa."""
    state = "IS NOT NULL" if removed else "IS NULL"
    sql = f"""
        SELECT id::text, address, provider_name, contact_phone, price_usd::float8, price_unit,
               width_m::float8, height_m::float8, type, location_precision,
               ST_Y(location) AS lat, ST_X(location) AS lng
        FROM billboards WHERE source = 'reporte' AND removed_at {state} ORDER BY updated_at DESC
    """
    with connect() as conn:
        return conn.execute(sql).fetchall()


# Solo las nacidas de un reporte: las de otras fuentes se corrigen en su CSV, o se pisarían al reimportarlo
@app.put("/api/billboards/{billboard_id}", status_code=204, dependencies=[Depends(require_admin)])
def edit_published_report(billboard_id: UUID, edit: BillboardEdit):
    sql = """
        UPDATE billboards SET address = COALESCE(%(address)s, address),
            provider_name = COALESCE(%(provider_name)s, 'Empresa por identificar'),
            contact_phone = %(contact_phone)s, price_usd = %(price_usd)s, price_unit = %(price_unit)s,
            type = %(type)s, width_m = %(width_m)s, height_m = %(height_m)s, updated_at = now()
        WHERE id = %(id)s AND source = 'reporte'
    """
    with connect() as conn:
        if not conn.execute(sql, {**edit.values(), "id": billboard_id}).rowcount:
            raise HTTPException(404, "Valla reportada no encontrada")


@app.post("/api/billboards/{billboard_id}/remove", status_code=204, dependencies=[Depends(require_admin)])
def remove_published_report(billboard_id: UUID):
    """Quita la valla del mapa sin borrarla: se puede restaurar."""
    sql = "UPDATE billboards SET removed_at = now(), updated_at = now() WHERE id = %s AND source = 'reporte'"
    update_billboard(billboard_id, sql)


@app.post("/api/billboards/{billboard_id}/restore", status_code=204, dependencies=[Depends(require_admin)])
def restore_published_report(billboard_id: UUID):
    sql = "UPDATE billboards SET removed_at = NULL, updated_at = now() WHERE id = %s AND source = 'reporte'"
    update_billboard(billboard_id, sql)


class MapsLink(BaseModel):
    url: str = Field(min_length=10, max_length=2000)


@app.post("/api/maps-link")
def read_maps_link(link: MapsLink):
    """Convierte un enlace de Google Maps en coordenadas, sin guardar nada."""
    try:
        coords = maps_link.resolve(link.url)
    except ValueError:
        raise HTTPException(422, "El enlace no es de Google Maps") from None
    if not coords:
        raise HTTPException(422, "Ese enlace no trae coordenadas")
    return {"lat": coords[0], "lng": coords[1]}


@app.get("/reportes", include_in_schema=False)
def reports_page():
    return FileResponse(Path(__file__).parent / "static" / "reportes.html")


@app.get("/api/providers")
def list_providers():
    """Empresas con su contacto público, cuántas vallas tienen y cuántas ya tienen ubicación."""
    sql = """
        SELECT b.provider_name, count(*) AS billboards, count(b.location) AS located,
               min(b.price_usd)::float8 AS min_price_usd, max(b.price_usd)::float8 AS max_price_usd,
               c.website, c.phone, c.email, c.address, c.source_url
        FROM billboards b LEFT JOIN provider_contacts c USING (provider_name)
        WHERE b.removed_at IS NULL
        GROUP BY b.provider_name, c.provider_name
        ORDER BY billboards DESC
    """
    with connect() as conn:
        return conn.execute(sql).fetchall()


@app.get("/api/coverage")
def coverage():
    """Qué tan completa está la información: totales por fuente y precisión de ubicación."""
    sql = """
        SELECT source, count(*) AS billboards,
               count(*) FILTER (WHERE location_precision = 'exacta' AND removed_at IS NULL) AS exact,
               count(*) FILTER (WHERE location_precision = 'aproximada' AND removed_at IS NULL) AS approximate,
               count(*) FILTER (WHERE location IS NULL AND removed_at IS NULL) AS without_location,
               count(*) FILTER (WHERE verified_at IS NOT NULL) AS verified,
               count(*) FILTER (WHERE removed_at IS NOT NULL) AS removed
        FROM billboards GROUP BY source ORDER BY source
    """
    with connect() as conn:
        return conn.execute(sql).fetchall()
