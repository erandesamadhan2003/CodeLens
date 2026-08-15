-- schema.sql
-- Migration file for dependency-engine microservice tables

CREATE TABLE IF NOT EXISTS vuln_cache (
    package TEXT NOT NULL,
    version TEXT NOT NULL,
    ecosystem TEXT NOT NULL,
    vulnerabilities JSONB NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    checked_at TIMESTAMP NOT NULL,
    UNIQUE (package, version, ecosystem)
);

CREATE TABLE IF NOT EXISTS dependency_reports (
    id UUID PRIMARY KEY,
    run_id UUID UNIQUE NOT NULL,
    total_dependencies INTEGER NOT NULL DEFAULT 0,
    vulnerable_count INTEGER NOT NULL DEFAULT 0,
    outdated_count INTEGER NOT NULL DEFAULT 0,
    critical_cves INTEGER NOT NULL DEFAULT 0,
    ecosystems JSONB NOT NULL DEFAULT '[]',
    dependencies JSONB NOT NULL DEFAULT '[]',
    cve_details JSONB NOT NULL DEFAULT '[]',
    text_summary TEXT,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_results (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL,
    engine TEXT NOT NULL,
    status TEXT NOT NULL,
    result_data JSONB,
    error_message TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    CONSTRAINT engine_results_run_id_engine_key UNIQUE (run_id, engine)
);
