"""Formato CSV común: toda fuente (CNE, Street View, agencias) se reduce a estas columnas."""
FIELDS = [
    "source", "source_ref", "provider_name", "province", "type", "address",
    "height_m", "width_m", "price_usd", "price_unit",
    "lat", "lng", "location_precision", "contact_email", "contact_phone", "notes",
]
