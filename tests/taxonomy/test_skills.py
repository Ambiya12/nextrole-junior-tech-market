import pytest
from pydantic import ValidationError

from nextrole.taxonomy import SkillCategory, SkillTaxonomy, load_default_taxonomy


def test_bundled_taxonomy_is_a_substantive_first_release() -> None:
    taxonomy = load_default_taxonomy()

    assert taxonomy.version == 1
    assert len(taxonomy.skills) >= 40
    assert set(SkillCategory).issubset({skill.category for skill in taxonomy.skills})


@pytest.mark.parametrize(
    ("term", "expected_slug"),
    [
        ("PowerBI", "power_bi"),
        ("  microsoft   power bi ", "power_bi"),
        ("POSTGRES", "postgresql"),
        ("Google Cloud", "gcp"),
        ("PySpark", "spark"),
    ],
)
def test_taxonomy_resolves_aliases(term: str, expected_slug: str) -> None:
    skill = load_default_taxonomy().resolve(term)

    assert skill is not None
    assert skill.slug == expected_slug


def test_taxonomy_returns_none_for_unknown_terms() -> None:
    assert load_default_taxonomy().resolve("not a real technology") is None


def test_taxonomy_rejects_duplicate_slugs() -> None:
    data = {
        "version": 1,
        "skills": [
            {"slug": "sql", "name": "SQL", "category": "programming_language"},
            {"slug": "sql", "name": "Another SQL", "category": "database"},
        ],
    }

    with pytest.raises(ValidationError, match="duplicate skill slug"):
        SkillTaxonomy.model_validate(data)


def test_taxonomy_rejects_aliases_shared_by_different_skills() -> None:
    data = {
        "version": 1,
        "skills": [
            {"slug": "postgresql", "name": "PostgreSQL", "category": "database"},
            {
                "slug": "other_database",
                "name": "Other Database",
                "category": "database",
                "aliases": ["postgresql"],
            },
        ],
    }

    with pytest.raises(ValidationError, match="term 'postgresql' is shared"):
        SkillTaxonomy.model_validate(data)
