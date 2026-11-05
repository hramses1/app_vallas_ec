# Marketplace de vallas

Directorio de vallas publicitarias de Ecuador: dónde están, de qué empresa son y cuánto cuestan aproximadamente. Quien quiere anunciar contacta directo a la empresa. Piloto: Guayaquil, Samborondón y Durán.

## Tecnologías

Vue 3 y Leaflet en el mapa, FastAPI en la API, y PostgreSQL con PostGIS en la base de datos. Todo corre con Docker Compose.

## Levantar

Necesitas Docker Desktop. Copia `.env.example` a `.env`, cambia las dos claves y ejecuta:

```bash
docker compose up -d --build
docker compose run --rm api python -m importers.load_csv /data/cne_2023.csv
docker compose run --rm api python -m importers.load_csv /data/bluenova_2026.csv
docker compose run --rm api python -m importers.load_contacts /data/contactos_empresas.csv
```

Documentación interactiva: http://127.0.0.1:8000/docs

## Mapa para el cliente

`docker compose up -d` también lo levanta, y vuelve a arrancar solo mientras Docker Desktop esté abierto.

Abre http://localhost:5173. Los datos llegan de la API por el proxy de Vite.

Prueba del flujo principal, con ambos activos: `python web/e2e/smoke.py` (requiere Playwright para Python). Prueba del formato de textos: `node web/e2e/format_check.mjs`.

## Endpoints

| Método | Ruta | Para qué |
|---|---|---|
| GET | `/api/billboards` | Vallas ubicadas en GeoJSON. Filtros: recuadro del mapa, sin el cual busca en todo el país (`min_lat`, `max_lat`, `min_lng`, `max_lng`), `type`, `min_price`, `max_price`, `provider`, `precision`, `q` (palabras en dirección o empresa, sin importar tildes). Con `located=false` trae las que aún no tienen punto |
| GET | `/api/billboards/{id}` | Ficha de una valla |
| GET | `/api/billboards/pending.csv` | Vallas sin coordenada exacta, para completarlas |
| GET | `/api/billboards/to-locate` | Lista de trabajo de la zona piloto |
| PUT | `/api/billboards/{id}/location` | Guarda la ubicación exacta (requiere `X-Admin-Token`) |
| POST | `/api/billboards/{id}/not-found` | Marca que la valla ya no existe (requiere `X-Admin-Token`) |
| POST | `/api/reports` | Recibe el reporte de una valla; no se publica hasta aprobarlo |
| GET | `/api/reports` | Reportes por revisar (requiere `X-Admin-Token`) |
| GET | `/api/reports/published` | Vallas publicadas desde reportes (requiere `X-Admin-Token`) |
| POST | `/api/billboards/{id}/remove` y `/restore` | Quita del mapa o restaura una valla publicada desde un reporte (requiere `X-Admin-Token`) |
| PUT | `/api/reports/{id}` y `/api/billboards/{id}` | Edita un reporte pendiente o una valla publicada desde un reporte (requiere `X-Admin-Token`) |
| POST | `/api/reports/{id}/approve` y `/reject` | Publica o descarta un reporte (requiere `X-Admin-Token`) |
| POST | `/api/maps-link` | Convierte un enlace de Google Maps en coordenadas |
| GET | `/api/providers` | Empresas con su contacto público, cuántas vallas tienen y cuántas están ubicadas |
| GET | `/api/coverage` | Qué tan completos están los datos, por fuente |

Recuadro de la zona piloto: `min_lat=-2.32&max_lat=-1.98&min_lng=-80.02&max_lng=-79.78`.

## De dónde salen los datos

`data/cne_2023.csv` viene del [tarifario de vallas del CNE](https://www.cne.gob.ec/wp-content/uploads/2023/07/Tarifario-Vallas.pdf), un PDF público.

Límites que hay que tener presentes:

- **Es de 2023.** Guayaquil ha retirado vallas desde entonces, así que una fila puede no existir ya. `verified_at` vacío significa que nadie lo ha confirmado.
- **Los precios son tarifas electorales por día**, no precios comerciales vigentes.
- **La provincia es la de registro de la empresa**, no siempre la de la valla.
- **No trae contactos.** Están en `data/contactos_empresas.csv`, tomados de lo que publica cada empresa; cada fila indica su fuente.

`data/bluenova_2026.csv` lista las piezas que [Blue Nova publica en su guía](https://bluenova.com.ec/vallas-publicitarias-guayaquil-guia-ooh-2026/), incluidas pantallas en puentes peatonales. Es un intermediario: no dice quién es el dueño de cada pieza, ni publica precios.

`location_precision` indica cuánto fiarse del punto:

- `exacta`: coordenadas de la fuente o de un relevamiento.
- `aproximada`: un punto de la vía o lugar que cita la dirección, que puede estar a kilómetros de la valla. Lo calcula `importers/locate_roads.py` con OpenStreetMap (© colaboradores de OpenStreetMap, licencia ODbL).

## Agregar o completar datos

Toda fuente se reduce al mismo CSV (`data/plantilla_recoleccion.csv`) y se carga igual:

```bash
docker compose run --rm api python -m importers.load_csv /data/mi_archivo.csv
```

Se puede repetir sin duplicar, porque actualiza por `source` + `source_ref`. Una celda vacía no borra datos, y una ubicación exacta no se pisa con una aproximada.

Para ubicar vallas una por una, abre http://127.0.0.1:8000/ubicar con el `ADMIN_TOKEN` de `.env`: guarda la coordenada o marca que la valla ya no existe. Antes de abrir la API a internet hay que servirla con HTTPS, porque esa clave viaja en cada guardado.

También se puede trabajar en lote: descarga `/api/billboards/pending.csv?province=GUAYAS`, llena `lat` y `lng`, guárdalo en `data/` y cárgalo. Para una valla nueva usa la plantilla con tu propio `source` (por ejemplo `streetview`).

Para regenerar el CSV del CNE desde el PDF:

```bash
cd api
python -m importers.cne_pdf ruta/Tarifario-Vallas.pdf ../data/cne_2023.csv
python -m importers.locate_roads ../data/cne_2023.csv
```

## Reportes de los usuarios

El botón del mapa permite reportar una valla que falta. Revisa los reportes en http://127.0.0.1:8000/reportes con el `ADMIN_TOKEN` de `.env`. Al aprobarlos, salen en el mapa como ubicación aproximada y pasan a la lista de `/ubicar` para confirmarlos.

Si la base ya existía, crea la tabla una sola vez:

```bash
docker compose exec db psql -U vallas -d vallas -f /docker-entrypoint-initdb.d/02_reports.sql
```

## Pruebas

```bash
docker compose run --rm api python -m tests.test_importers
```
