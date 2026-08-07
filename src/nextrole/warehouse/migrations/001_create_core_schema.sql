CREATE TABLE pipeline_runs (
    run_id UUID PRIMARY KEY,
    source TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    records_extracted INTEGER NOT NULL DEFAULT 0 CHECK (records_extracted >= 0),
    records_loaded INTEGER NOT NULL DEFAULT 0 CHECK (records_loaded >= 0),
    records_rejected INTEGER NOT NULL DEFAULT 0 CHECK (records_rejected >= 0),
    duplicates_found INTEGER NOT NULL DEFAULT 0 CHECK (duplicates_found >= 0),
    error_message TEXT,
    CHECK (
        (status = 'running' AND completed_at IS NULL)
        OR (status IN ('succeeded', 'failed') AND completed_at IS NOT NULL)
    )
);

CREATE TABLE job_postings (
    job_id CHAR(64) PRIMARY KEY CHECK (job_id ~ '^[a-f0-9]{64}$'),
    source TEXT NOT NULL,
    source_job_id TEXT NOT NULL,
    title TEXT NOT NULL,
    normalized_role TEXT NOT NULL,
    company_name TEXT,
    location_text TEXT,
    city TEXT,
    region TEXT,
    contract_type TEXT NOT NULL,
    experience_level TEXT NOT NULL,
    education_level TEXT,
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    salary_currency CHAR(3),
    salary_period TEXT,
    work_mode TEXT NOT NULL,
    description TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    first_seen_at TIMESTAMPTZ NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL,
    source_url TEXT NOT NULL,
    UNIQUE (source, source_job_id),
    CHECK (salary_min IS NULL OR salary_min >= 0),
    CHECK (salary_max IS NULL OR salary_max >= 0),
    CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
    CHECK (first_seen_at <= last_seen_at)
);

CREATE TABLE skills (
    skill_slug TEXT PRIMARY KEY CHECK (skill_slug ~ '^[a-z0-9]+(_[a-z0-9]+)*$'),
    skill_name TEXT NOT NULL UNIQUE,
    skill_category TEXT NOT NULL,
    taxonomy_version INTEGER NOT NULL CHECK (taxonomy_version >= 1)
);

CREATE TABLE job_skills (
    job_id CHAR(64) NOT NULL REFERENCES job_postings(job_id) ON DELETE CASCADE,
    skill_slug TEXT NOT NULL REFERENCES skills(skill_slug),
    matched_term TEXT NOT NULL,
    evidence TEXT NOT NULL,
    match_start INTEGER NOT NULL CHECK (match_start >= 0),
    match_end INTEGER NOT NULL CHECK (match_end > match_start),
    extraction_method TEXT NOT NULL,
    PRIMARY KEY (job_id, skill_slug)
);

CREATE TABLE duplicate_observations (
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    job_id CHAR(64) NOT NULL REFERENCES job_postings(job_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_job_id TEXT NOT NULL,
    discarded_collected_at TIMESTAMPTZ NOT NULL,
    retained_collected_at TIMESTAMPTZ NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (run_id, job_id, discarded_collected_at)
);

CREATE TABLE rejected_records (
    rejection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES pipeline_runs(run_id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    source_job_id TEXT,
    pipeline_stage TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload JSONB NOT NULL,
    rejected_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_postings_role ON job_postings(normalized_role);
CREATE INDEX idx_job_postings_city ON job_postings(city);
CREATE INDEX idx_job_postings_contract ON job_postings(contract_type);
CREATE INDEX idx_job_postings_published_at ON job_postings(published_at);
CREATE INDEX idx_job_skills_skill ON job_skills(skill_slug);
CREATE INDEX idx_rejected_records_run ON rejected_records(run_id);
