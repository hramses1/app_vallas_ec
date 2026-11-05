-- Vallas que reportan los usuarios. Nada se publica hasta que alguien lo aprueba.
CREATE TABLE IF NOT EXISTS billboard_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location GEOMETRY(Point, 4326) NOT NULL,
    address TEXT,  -- opcional: el punto basta; al aprobar se busca en OpenStreetMap
    provider_name TEXT,
    contact_phone TEXT,
    price_usd NUMERIC(10, 2),
    price_unit TEXT CHECK (price_unit IN ('dia', 'mes')),
    width_m NUMERIC(6, 2),
    height_m NUMERIC(6, 2),
    type TEXT NOT NULL CHECK (type IN ('estatica', 'digital', 'mupi', 'puente', 'movil')),
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'pendiente' CHECK (status IN ('pendiente', 'aprobado', 'rechazado')),
    billboard_id UUID REFERENCES billboards (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billboard_reports_created ON billboard_reports (created_at);
