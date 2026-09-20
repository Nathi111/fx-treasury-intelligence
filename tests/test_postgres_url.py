from src.load.postgres import normalise_database_url


def test_normalise_neon_postgresql_url_to_psycopg_v3():
    url = "postgresql://user:secret@example.neon.tech/db?sslmode=require"
    assert (
        normalise_database_url(url)
        == "postgresql+psycopg://user:secret@example.neon.tech/db?sslmode=require"
    )


def test_preserve_explicit_sqlalchemy_driver_url():
    url = "postgresql+psycopg://user:secret@example.neon.tech/db"
    assert normalise_database_url(url) == url
