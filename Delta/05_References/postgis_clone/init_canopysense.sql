-- Database Schema for Canopy Sense 
CREATE SCHEMA IF NOT EXISTS canopysense;
SET search_path TO canopysense, public;

-- 1. Tabel users
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(150) UNIQUE,
    full_name VARCHAR(150),
    username VARCHAR(150),
    phone_number VARCHAR(20),
    is_global_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Tabel estates
CREATE TABLE estates (
 id SERIAL PRIMARY KEY,
 name VARCHAR(100) NOT NULL,
 code VARCHAR(20) UNIQUE NOT NULL,
 geometry GEOMETRY(MultiPolygonZ,4326) NOT NULL,
 envelope GEOMETRY GENERATED ALWAYS AS (ST_Envelope(geometry)) STORED,
 area_ha NUMERIC(10,2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED,
 is_valid BOOLEAN GENERATED ALWAYS AS (ST_IsValid(geometry)) STORED,
 created_at TIMESTAMP DEFAULT NOW(),
 updated_at TIMESTAMP
);

CREATE INDEX idx_estates_geom ON estates USING GIST(geometry);
CREATE INDEX idx_estates_envelope ON estates USING GIST(envelope);
CREATE INDEX idx_estates_code ON estates(code);
ALTER TABLE estates ADD CONSTRAINT chk_estate_valid CHECK (ST_IsValid(geometry) AND ST_SRID(geometry)=4326);

-- 3. Tabel afdelings
CREATE TABLE afdelings (
    id SERIAL PRIMARY KEY,
    estate_id INTEGER REFERENCES estates(id),
    name VARCHAR(100),
    code VARCHAR(20),
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL
);

CREATE INDEX idx_afdelings_geom ON afdelings USING GIST(geometry);
CREATE INDEX idx_afdelings_estate ON afdelings(estate_id);
ALTER TABLE afdelings ADD CONSTRAINT chk_afdeling_type CHECK (GeometryType(geometry) = 'MULTIPOLYGON');

-- 4. Tabel blocks
CREATE TABLE blocks (
    id SERIAL PRIMARY KEY,
    afdeling_id INTEGER REFERENCES afdelings(id),
    name VARCHAR(100),
    code VARCHAR(20) UNIQUE,
    geometry GEOMETRY(Polygon, 4326) NOT NULL,
    plant_year INTEGER,
    clone_type VARCHAR(50),
    area_ha NUMERIC(10, 2) GENERATED ALWAYS AS (ST_Area(geometry::geography)/10000) STORED
);

ALTER TABLE blocks ADD CONSTRAINT chk_blocks_type CHECK (GeometryType(geometry) = 'POLYGON');
CREATE INDEX idx_blocks_geometry ON blocks USING GIST (geometry);

-- 5. Tabel satellite_data
CREATE TABLE satellite_data (
    id SERIAL PRIMARY KEY,
    block_id INTEGER REFERENCES blocks(id),
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

CREATE INDEX idx_satellite_date_block ON satellite_data (block_id, acquisition_date DESC);

-- 6. Tabel backfill_skipped
CREATE TABLE backfill_skipped (
    id           SERIAL PRIMARY KEY,
    window_start DATE NOT NULL,
    window_end   DATE NOT NULL,
    skip_reason  TEXT NOT NULL,
    skipped_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (window_start, window_end)
);

-- 7. Tabel ground_truth
CREATE TABLE ground_truth (
    id SERIAL PRIMARY KEY,
    block_id INTEGER REFERENCES blocks(id),
    satellite_data_id INTEGER REFERENCES satellite_data(id),
    measurement_date DATE,
    gcc_percent NUMERIC(5, 2),
    method VARCHAR(50),
    observer VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 8. Tabel predictions
CREATE TABLE predictions (
    id SERIAL PRIMARY KEY,
    satellite_data_id INTEGER REFERENCES satellite_data(id),
    prediction_date DATE,
    gcc_predicted FLOAT,
    gcc_confidence FLOAT,
    model_version VARCHAR(30),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(satellite_data_id, model_version)
);

-- 9. Tabel anomalies
CREATE TABLE anomalies (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER REFERENCES predictions(id) UNIQUE,
    actual_gcc FLOAT,
    deviation FLOAT,
    status VARCHAR(20) DEFAULT 'OPEN',
    detected_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES users(id),
    notes TEXT,
    CONSTRAINT chk_status CHECK (status IN ('OPEN', 'VERIFIED', 'FALSE_POSITIVE', 'RESOLVED'))
);

-- 10. Tabel alerts
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    anomaly_id INTEGER REFERENCES anomalies(id),
    user_id INTEGER REFERENCES users(id),
    alert_type VARCHAR(50),
    priority VARCHAR(20),
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 11. Tabel field_inspections
CREATE TABLE field_inspections (
    id SERIAL PRIMARY KEY,
    anomaly_id INTEGER REFERENCES anomalies(id) UNIQUE,
    inspector_id INTEGER REFERENCES users(id),
    actual_gcc FLOAT,
    notes TEXT,
    photos JSONB,
    inspected_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 12. Tabel user_estate_roles
CREATE TABLE user_estate_roles (
    user_id INTEGER REFERENCES users(id),
    scope_id INTEGER,
    scope_type VARCHAR(50),
    role VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (user_id, scope_id, scope_type)
);
