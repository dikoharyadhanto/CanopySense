-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Ensure public tables land in public regardless of role-level search_path
SET search_path TO public;

-- Namespace for patcher-facing operational tables (patcher_local.py contract)
CREATE SCHEMA IF NOT EXISTS canopysense;

-- 1. companies
CREATE TABLE companies (
  id BIGSERIAL PRIMARY KEY,
  company_id UUID UNIQUE NOT NULL,
  company_name VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  metadata JSONB DEFAULT '{}'
);

-- 2. themes
CREATE TABLE themes (
  id BIGSERIAL PRIMARY KEY,
  theme_name VARCHAR(100),
  light_colors JSONB,
  dark_colors JSONB,
  created_at TIMESTAMP DEFAULT NOW()
);

-- 3. company_settings
CREATE TABLE company_settings (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  app_title VARCHAR(255) DEFAULT 'CanopySense',
  logo_url VARCHAR(500),
  theme_id BIGINT REFERENCES themes(id),
  custom_css TEXT,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. users
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    company_id BIGINT REFERENCES companies(id),
    email VARCHAR(150) UNIQUE,
    full_name VARCHAR(150),
    username VARCHAR(150),
    password_hash VARCHAR(255), -- Added for local auth
    phone_number VARCHAR(20),
    is_global_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by BIGINT REFERENCES users(id),
    updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. company_invitations
CREATE TABLE company_invitations (
  id BIGSERIAL PRIMARY KEY,
  company_id BIGINT REFERENCES companies(id),
  token VARCHAR(255) UNIQUE NOT NULL,
  email VARCHAR(255) NOT NULL,
  role VARCHAR(50) DEFAULT 'viewer',
  created_at TIMESTAMP DEFAULT NOW(),
  expires_at TIMESTAMP DEFAULT NOW() + INTERVAL '7 days',
  accepted_at TIMESTAMP,
  accepted_by_user_id BIGINT REFERENCES users(id)
);

-- 6. user_company_roles
CREATE TABLE user_company_roles (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT REFERENCES users(id),
  company_id BIGINT REFERENCES companies(id),
  role VARCHAR(50) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  promoted_by BIGINT REFERENCES users(id),
  UNIQUE(user_id, company_id)
);

-- 7. canopysense.estates (patcher contract: canopysense schema)
CREATE TABLE canopysense.estates (
 id BIGSERIAL PRIMARY KEY,
 company_id BIGINT REFERENCES public.companies(id),
 name VARCHAR(100) NOT NULL,
 code VARCHAR(20) UNIQUE NOT NULL,
 geometry GEOMETRY(MultiPolygonZ,4326) NOT NULL,
 envelope GEOMETRY GENERATED ALWAYS AS (ST_Envelope(geometry)) STORED,
 area_ha NUMERIC(10,2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED,
 is_valid BOOLEAN GENERATED ALWAYS AS (ST_IsValid(geometry)) STORED,
 created_at TIMESTAMP DEFAULT NOW(),
 updated_at TIMESTAMP
);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estates_geom ON canopysense.estates USING GIST(geometry);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estates_envelope ON canopysense.estates USING GIST(envelope);
CREATE INDEX idx_estates_code ON canopysense.estates(code);
CREATE INDEX idx_estates_company_id ON canopysense.estates(company_id);
ALTER TABLE canopysense.estates ADD CONSTRAINT chk_estate_valid CHECK (ST_IsValid(geometry) AND ST_SRID(geometry)=4326);

-- 8. canopysense.afdelings (patcher contract: canopysense schema)
CREATE TABLE canopysense.afdelings (
    id BIGSERIAL PRIMARY KEY,
    estate_id BIGINT REFERENCES canopysense.estates(id),
    company_id BIGINT REFERENCES public.companies(id),
    name VARCHAR(100),
    code VARCHAR(20),
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL
);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_afdelings_geom ON canopysense.afdelings USING GIST(geometry);
CREATE INDEX idx_afdelings_estate ON canopysense.afdelings(estate_id);
ALTER TABLE canopysense.afdelings ADD CONSTRAINT chk_afdeling_type CHECK (GeometryType(geometry) = 'MULTIPOLYGON');

-- 9. canopysense.blocks (patcher contract: hardcoded in patcher_local.py line 51)
CREATE TABLE canopysense.blocks (
    id BIGSERIAL PRIMARY KEY,
    afdeling_id BIGINT REFERENCES canopysense.afdelings(id),
    company_id BIGINT REFERENCES public.companies(id),
    name VARCHAR(100),
    code VARCHAR(20) UNIQUE,
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    plant_year INTEGER,
    clone_type VARCHAR(50),
    area_ha NUMERIC(10, 2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED
);
ALTER TABLE canopysense.blocks ADD CONSTRAINT chk_blocks_type CHECK (GeometryType(geometry) = 'POLYGON');
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_blocks_geom ON canopysense.blocks USING GIST(geometry);
CREATE INDEX idx_blocks_company_id ON canopysense.blocks(company_id);

-- 10. canopysense.satellite_data (patcher contract: written by Cloud Function via _execute_writes)
CREATE TABLE canopysense.satellite_data (
    id BIGSERIAL PRIMARY KEY,
    block_id BIGINT REFERENCES canopysense.blocks(id),
    acquisition_date DATE,
    sensor VARCHAR(20) DEFAULT 'sentinel-2',
    cloud_cover NUMERIC(5, 2),
    ndvi FLOAT,
    evi FLOAT,
    ndre FLOAT,
    savi FLOAT,
    gndvi FLOAT,
    features JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(block_id, acquisition_date, sensor)
);
CREATE INDEX idx_satellite_date_block ON canopysense.satellite_data (block_id, acquisition_date DESC);

-- Trigger to make satellite_data append-only
CREATE OR REPLACE FUNCTION canopysense.prevent_satellite_data_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'satellite_data is an append-only table. Updates or deletes are not allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER immutable_satellite_data
BEFORE UPDATE OR DELETE ON canopysense.satellite_data
FOR EACH ROW EXECUTE FUNCTION canopysense.prevent_satellite_data_update();

-- 16. canopysense.patcher_run_log (patcher contract: written by patcher_local.py)
CREATE TABLE canopysense.patcher_run_log (
    id BIGSERIAL PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    trigger_mode VARCHAR(20) NOT NULL,
    afdeling_id INTEGER,
    block_id INTEGER,
    batch_fingerprint VARCHAR(64),
    status VARCHAR(20) NOT NULL,
    rows_inserted INTEGER DEFAULT 0,
    error_detail TEXT,
    api_version VARCHAR(10),
    started_at TIMESTAMP,
    triggered_at TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_patcher_run_log_afdeling ON canopysense.patcher_run_log (afdeling_id, triggered_at DESC);
CREATE INDEX idx_patcher_run_log_status ON canopysense.patcher_run_log (status, trigger_mode);

-- 11. ground_truth (public schema — Phase 2+ ML tables)
CREATE TABLE ground_truth (
    id BIGSERIAL PRIMARY KEY,
    block_id BIGINT REFERENCES canopysense.blocks(id),
    satellite_data_id BIGINT REFERENCES canopysense.satellite_data(id),
    measurement_date DATE,
    gcc_percent NUMERIC(5, 2),
    method VARCHAR(50),
    observer VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 12. predictions
CREATE TABLE predictions (
    id BIGSERIAL PRIMARY KEY,
    satellite_data_id BIGINT REFERENCES canopysense.satellite_data(id),
    prediction_date DATE,
    gcc_predicted FLOAT,
    gcc_confidence FLOAT,
    model_version VARCHAR(30),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(satellite_data_id, model_version)
);
CREATE INDEX idx_predictions_date_block ON predictions (satellite_data_id, prediction_date DESC);

-- 13. anomalies
CREATE TABLE anomalies (
    id BIGSERIAL PRIMARY KEY,
    prediction_id BIGINT REFERENCES predictions(id) UNIQUE,
    block_id BIGINT REFERENCES canopysense.blocks(id),
    actual_gcc FLOAT,
    deviation FLOAT,
    status VARCHAR(20) DEFAULT 'OPEN',
    detected_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    reviewed_by BIGINT REFERENCES users(id),
    notes TEXT,
    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'VERIFIED', 'FALSE_POSITIVE', 'RESOLVED'))
);
CREATE INDEX idx_anomalies_detection_block ON anomalies (block_id, detected_at DESC);

-- 14. alerts
CREATE TABLE alerts (
    id BIGSERIAL PRIMARY KEY,
    anomaly_id BIGINT REFERENCES anomalies(id),
    user_id BIGINT REFERENCES users(id),
    alert_type VARCHAR(50),
    priority VARCHAR(20),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 15. field_inspections
CREATE TABLE field_inspections (
    id BIGSERIAL PRIMARY KEY,
    anomaly_id BIGINT REFERENCES anomalies(id) UNIQUE,
    inspector_id BIGINT REFERENCES users(id),
    actual_gcc FLOAT,
    notes TEXT,
    photos JSONB,
    inspected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Set default search_path: canopysense first so unqualified backend queries resolve correctly
ALTER ROLE postgres SET search_path = canopysense, public;
