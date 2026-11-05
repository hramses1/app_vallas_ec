CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE TABLE billboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source TEXT NOT NULL,        -- de dónde salió el dato: cne_2023, streetview, agencia...
    source_ref TEXT NOT NULL,    -- identificador dentro de esa fuente
    provider_name TEXT NOT NULL,
    province TEXT,               -- en el CNE es la provincia de registro, no siempre la de la valla
    type TEXT NOT NULL CHECK (type IN ('estatica', 'digital', 'mupi', 'puente', 'movil')),
    address TEXT NOT NULL,
    height_m NUMERIC(6, 2),
    width_m NUMERIC(6, 2),
    price_usd NUMERIC(10, 2),
    price_unit TEXT CHECK (price_unit IN ('hora', 'dia', 'mes')),
    location GEOMETRY(Point, 4326),
    -- exacta: coordenadas de la fuente o de un relevamiento. aproximada: un punto de la vía o lugar citado.
    location_precision TEXT CHECK (location_precision IN ('exacta', 'aproximada')),
    contact_email TEXT,
    contact_phone TEXT,
    notes TEXT,
    verified_at TIMESTAMPTZ,     -- NULL: nadie confirmó todavía que la valla siga en pie
    removed_at TIMESTAMPTZ,      -- alguien comprobó que ya no existe; deja de listarse
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_ref),
    CHECK ((location IS NULL) = (location_precision IS NULL))
);

CREATE INDEX idx_billboards_location ON billboards USING GIST (location);

-- Contactos que cada empresa publica. Solo canales de la empresa, no datos de personas.
CREATE TABLE provider_contacts (
    provider_name TEXT PRIMARY KEY,
    website TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    source_url TEXT NOT NULL
);
