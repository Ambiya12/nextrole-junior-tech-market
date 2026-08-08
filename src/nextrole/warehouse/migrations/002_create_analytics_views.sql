CREATE OR REPLACE VIEW analytics_market_overview AS
SELECT
    COUNT(*)::BIGINT AS total_postings,
    COUNT(DISTINCT company_name)::BIGINT AS unique_companies,
    COUNT(DISTINCT city)::BIGINT AS unique_cities,
    COUNT(*) FILTER (WHERE contract_type = 'apprenticeship')::BIGINT
        AS apprenticeship_postings,
    COUNT(*) FILTER (WHERE contract_type = 'internship')::BIGINT
        AS internship_postings,
    COUNT(*) FILTER (WHERE contract_type = 'permanent')::BIGINT
        AS permanent_postings,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE work_mode = 'remote')
        / NULLIF(COUNT(*), 0),
        1
    ) AS remote_percentage,
    MIN(published_at) AS earliest_publication,
    MAX(published_at) AS latest_publication,
    MIN(first_seen_at) AS collection_window_start,
    MAX(last_seen_at) AS collection_window_end
FROM job_postings;

CREATE OR REPLACE VIEW analytics_role_summary AS
WITH skill_counts AS (
    SELECT job_id, COUNT(*)::INTEGER AS skill_count
    FROM job_skills
    GROUP BY job_id
)
SELECT
    jobs.normalized_role,
    COUNT(*)::BIGINT AS posting_count,
    COUNT(DISTINCT jobs.company_name)::BIGINT AS company_count,
    COUNT(DISTINCT jobs.city)::BIGINT AS city_count,
    COUNT(*) FILTER (WHERE jobs.work_mode = 'remote')::BIGINT AS remote_count,
    COUNT(*) FILTER (WHERE jobs.work_mode = 'hybrid')::BIGINT AS hybrid_count,
    ROUND(AVG(COALESCE(skill_counts.skill_count, 0)), 2) AS average_skills_per_posting
FROM job_postings AS jobs
LEFT JOIN skill_counts USING (job_id)
GROUP BY jobs.normalized_role;

CREATE OR REPLACE VIEW analytics_skill_demand AS
SELECT
    skills.skill_slug,
    skills.skill_name,
    skills.skill_category,
    COUNT(DISTINCT job_skills.job_id)::BIGINT AS posting_count,
    ROUND(
        100.0 * COUNT(DISTINCT job_skills.job_id)
        / NULLIF((SELECT COUNT(*) FROM job_postings), 0),
        1
    ) AS posting_percentage
FROM skills
LEFT JOIN job_skills USING (skill_slug)
GROUP BY skills.skill_slug, skills.skill_name, skills.skill_category;

CREATE OR REPLACE VIEW analytics_role_skill_demand AS
WITH role_totals AS (
    SELECT normalized_role, COUNT(*)::BIGINT AS posting_count
    FROM job_postings
    GROUP BY normalized_role
)
SELECT
    jobs.normalized_role,
    skills.skill_slug,
    skills.skill_name,
    skills.skill_category,
    COUNT(DISTINCT jobs.job_id)::BIGINT AS posting_count,
    ROUND(
        100.0 * COUNT(DISTINCT jobs.job_id)
        / NULLIF(role_totals.posting_count, 0),
        1
    ) AS role_posting_percentage
FROM job_postings AS jobs
JOIN job_skills USING (job_id)
JOIN skills USING (skill_slug)
JOIN role_totals USING (normalized_role)
GROUP BY
    jobs.normalized_role,
    role_totals.posting_count,
    skills.skill_slug,
    skills.skill_name,
    skills.skill_category;

CREATE OR REPLACE VIEW analytics_city_demand AS
SELECT
    city,
    region,
    COUNT(*)::BIGINT AS posting_count,
    COUNT(DISTINCT company_name)::BIGINT AS company_count,
    COUNT(DISTINCT normalized_role)::BIGINT AS role_count,
    COUNT(*) FILTER (WHERE work_mode IN ('remote', 'hybrid'))::BIGINT
        AS flexible_work_count
FROM job_postings
WHERE city IS NOT NULL
GROUP BY city, region;

CREATE OR REPLACE VIEW analytics_skill_transferability AS
SELECT
    skills.skill_slug,
    skills.skill_name,
    skills.skill_category,
    COUNT(DISTINCT jobs.normalized_role)::BIGINT AS role_count,
    COUNT(DISTINCT jobs.job_id)::BIGINT AS posting_count
FROM skills
JOIN job_skills USING (skill_slug)
JOIN job_postings AS jobs USING (job_id)
GROUP BY skills.skill_slug, skills.skill_name, skills.skill_category;

CREATE OR REPLACE VIEW analytics_skill_pairs AS
SELECT
    first_skill.skill_slug AS first_skill_slug,
    first_definition.skill_name AS first_skill_name,
    second_skill.skill_slug AS second_skill_slug,
    second_definition.skill_name AS second_skill_name,
    COUNT(DISTINCT first_skill.job_id)::BIGINT AS posting_count
FROM job_skills AS first_skill
JOIN job_skills AS second_skill
    ON first_skill.job_id = second_skill.job_id
    AND first_skill.skill_slug < second_skill.skill_slug
JOIN skills AS first_definition ON first_definition.skill_slug = first_skill.skill_slug
JOIN skills AS second_definition ON second_definition.skill_slug = second_skill.skill_slug
GROUP BY
    first_skill.skill_slug,
    first_definition.skill_name,
    second_skill.skill_slug,
    second_definition.skill_name;

CREATE OR REPLACE VIEW analytics_job_skill_profile AS
SELECT
    jobs.job_id,
    jobs.normalized_role,
    jobs.title,
    jobs.company_name,
    jobs.city,
    jobs.contract_type,
    jobs.work_mode,
    jobs.published_at,
    COALESCE(
        ARRAY_AGG(job_skills.skill_slug ORDER BY job_skills.skill_slug)
            FILTER (WHERE job_skills.skill_slug IS NOT NULL),
        ARRAY[]::TEXT[]
    ) AS skill_slugs
FROM job_postings AS jobs
LEFT JOIN job_skills USING (job_id)
GROUP BY jobs.job_id;
