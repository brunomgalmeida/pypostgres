-- =============================================================================
-- Base tables (no partitioning)
-- =============================================================================

CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    total DECIMAL(10, 2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_product ON orders(product_id);

-- =============================================================================
-- 1. RANGE partitioning — events by date (monthly partitions)
-- =============================================================================

CREATE TABLE events (
    id          SERIAL,
    event_type  VARCHAR(50) NOT NULL,
    payload     JSONB,
    recorded_at DATE NOT NULL
) PARTITION BY RANGE (recorded_at);

CREATE TABLE events_2026_01 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE events_2026_02 PARTITION OF events
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');

CREATE TABLE events_2026_03 PARTITION OF events
    FOR VALUES FROM ('2026-03-01') TO ('2026-04-01');

CREATE TABLE events_2026_04 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE TABLE events_2026_05 PARTITION OF events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');

CREATE TABLE events_2026_06 PARTITION OF events
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE events_default PARTITION OF events DEFAULT;

CREATE INDEX idx_events_recorded_at ON events (recorded_at);

-- =============================================================================
-- 2. LIST partitioning — sales by region
-- =============================================================================

CREATE TABLE sales (
    id          SERIAL,
    region      VARCHAR(20) NOT NULL,
    product_id  INTEGER REFERENCES products(id),
    amount      DECIMAL(12, 2) NOT NULL,
    sold_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) PARTITION BY LIST (region);

CREATE TABLE sales_emea PARTITION OF sales
    FOR VALUES IN ('EU', 'UK', 'DACH', 'NORDICS', 'MEA');

CREATE TABLE sales_americas PARTITION OF sales
    FOR VALUES IN ('US', 'CANADA', 'LATAM');

CREATE TABLE sales_apac PARTITION OF sales
    FOR VALUES IN ('ANZ', 'JAPAN', 'KOREA', 'SEA', 'INDIA');

CREATE TABLE sales_default PARTITION OF sales DEFAULT;

CREATE INDEX idx_sales_region ON sales (region);

-- =============================================================================
-- 3. HASH partitioning — sessions by user_id (4 partitions)
-- =============================================================================

CREATE TABLE sessions (
    id          SERIAL,
    user_id     INTEGER NOT NULL,
    token       VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at  TIMESTAMP NOT NULL
) PARTITION BY HASH (user_id);

CREATE TABLE sessions_p0 PARTITION OF sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 0);

CREATE TABLE sessions_p1 PARTITION OF sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 1);

CREATE TABLE sessions_p2 PARTITION OF sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 2);

CREATE TABLE sessions_p3 PARTITION OF sessions
    FOR VALUES WITH (MODULUS 4, REMAINDER 3);

CREATE INDEX idx_sessions_user ON sessions (user_id);

-- =============================================================================
-- 4. Multi-column range partitioning — metrics by (host, recorded_at)
-- =============================================================================

CREATE TABLE metrics (
    host        VARCHAR(100) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    recorded_at TIMESTAMP NOT NULL
) PARTITION BY RANGE (host, recorded_at);

CREATE TABLE metrics_web01 PARTITION OF metrics
    FOR VALUES FROM ('web01', '2026-01-01') TO ('web01', '2027-01-01');

CREATE TABLE metrics_web02 PARTITION OF metrics
    FOR VALUES FROM ('web02', '2026-01-01') TO ('web02', '2027-01-01');

CREATE TABLE metrics_db01 PARTITION OF metrics
    FOR VALUES FROM ('db01', '2026-01-01') TO ('db01', '2027-01-01');

-- =============================================================================
-- 5. Sub-partitioning — events range by date, then list by event_type
-- =============================================================================

CREATE TABLE events_detailed (
    id          SERIAL,
    event_type  VARCHAR(50) NOT NULL,
    payload     JSONB,
    recorded_at DATE NOT NULL
) PARTITION BY RANGE (recorded_at);

CREATE TABLE events_detailed_2026_01 PARTITION OF events_detailed
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01')
    PARTITION BY LIST (event_type);

CREATE TABLE events_detailed_2026_01_clicks PARTITION OF events_detailed_2026_01
    FOR VALUES IN ('click', 'tap', 'hover');

CREATE TABLE events_detailed_2026_01_views PARTITION OF events_detailed_2026_01
    FOR VALUES IN ('pageview', 'screenview');

CREATE TABLE events_detailed_2026_01_other PARTITION OF events_detailed_2026_01
    DEFAULT;

CREATE TABLE events_detailed_2026_02 PARTITION OF events_detailed
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01')
    PARTITION BY LIST (event_type);

CREATE TABLE events_detailed_2026_02_clicks PARTITION OF events_detailed_2026_02
    FOR VALUES IN ('click', 'tap', 'hover');

CREATE TABLE events_detailed_2026_02_views PARTITION OF events_detailed_2026_02
    FOR VALUES IN ('pageview', 'screenview');

CREATE TABLE events_detailed_2026_02_other PARTITION OF events_detailed_2026_02
    DEFAULT;

CREATE INDEX idx_events_detailed_recorded ON events_detailed (recorded_at);

-- =============================================================================
-- 6. Inheritance-based partitioning (legacy, trigger-routed)
-- =============================================================================

CREATE TABLE logs (
    level       VARCHAR(10) NOT NULL,
    message     TEXT NOT NULL,
    logged_at   DATE NOT NULL
);

CREATE TABLE logs_2026_01 (
    CHECK ( logged_at >= DATE '2026-01-01' AND logged_at < DATE '2026-02-01' )
) INHERITS (logs);

CREATE TABLE logs_2026_02 (
    CHECK ( logged_at >= DATE '2026-02-01' AND logged_at < DATE '2026-03-01' )
) INHERITS (logs);

CREATE TABLE logs_2026_03 (
    CHECK ( logged_at >= DATE '2026-03-01' AND logged_at < DATE '2026-04-01' )
) INHERITS (logs);

CREATE INDEX idx_logs_2026_01_logged ON logs_2026_01 (logged_at);
CREATE INDEX idx_logs_2026_02_logged ON logs_2026_02 (logged_at);
CREATE INDEX idx_logs_2026_03_logged ON logs_2026_03 (logged_at);

CREATE OR REPLACE FUNCTION logs_insert_trigger()
RETURNS TRIGGER AS $$
BEGIN
    IF ( NEW.logged_at >= DATE '2026-01-01' AND
         NEW.logged_at < DATE '2026-02-01' ) THEN
        INSERT INTO logs_2026_01 VALUES (NEW.*);
    ELSIF ( NEW.logged_at >= DATE '2026-02-01' AND
            NEW.logged_at < DATE '2026-03-01' ) THEN
        INSERT INTO logs_2026_02 VALUES (NEW.*);
    ELSIF ( NEW.logged_at >= DATE '2026-03-01' AND
            NEW.logged_at < DATE '2026-04-01' ) THEN
        INSERT INTO logs_2026_03 VALUES (NEW.*);
    ELSE
        RAISE EXCEPTION 'Date out of range. Fix the logs_insert_trigger() function!';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER insert_logs_trigger
    BEFORE INSERT ON logs
    FOR EACH ROW EXECUTE FUNCTION logs_insert_trigger();
