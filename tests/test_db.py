"""Data model validation, connection rules, and building tables from raw files."""
import duckdb
import pytest

from cardiac_imaging import config
from cardiac_imaging.db import build, connection, schema


def test_synthetic_db_matches_data_model(con):
    """The synthetic database (built from the schema) validates cleanly."""
    assert schema.validate(con) == []


def test_validate_reports_missing_wrong_and_extra(tmp_path):
    """validate() names missing tables, wrong types, missing and undocumented columns."""
    c = duckdb.connect(str(tmp_path / 'bad.duckdb'))
    c.execute("CREATE TABLE state_ffs_enrollment (year VARCHAR, state VARCHAR, surprise INTEGER)")
    problems = schema.validate(c)
    assert any('missing table partb_provider_service' in p for p in problems)
    assert any('state_ffs_enrollment.year is VARCHAR' in p for p in problems)
    assert any('state_ffs_enrollment.ffs missing' in p for p in problems)
    assert any('undocumented columns' in p and 'surprise' in p for p in problems)


def test_schema_documents_every_used_column():
    """Each table lists columns with a type, a meaning and a used flag; key analysis columns are flagged used."""
    for t in schema.TABLES:
        for col, typ, meaning, used in t['columns']:
            assert col and typ and meaning and isinstance(used, bool)
    used = {c for c, _, _, u in schema.CLAIMS_COLUMNS if u}
    assert {'HCPCS_Cd', 'Tot_Srvcs', 'Rndrng_Prvdr_RUCA', 'Rndrng_Prvdr_Type', 'Rndrng_NPI'} <= used


def test_read_only_connection_requires_existing_file(tmp_path):
    """Opening a missing local database read-only fails with a helpful message."""
    with pytest.raises(RuntimeError, match='No database'):
        connection.get_connection(str(tmp_path / 'nope.duckdb'))


def test_motherduck_needs_token(monkeypatch):
    """md: databases require MOTHERDUCK_TOKEN."""
    monkeypatch.delenv('MOTHERDUCK_TOKEN', raising=False)
    with pytest.raises(RuntimeError, match='MOTHERDUCK_TOKEN'):
        connection.get_connection('md:anything')


def test_require_tables(con, tmp_path):
    """require_tables passes on a full DB and names what's missing otherwise."""
    connection.require_tables(con)
    empty = duckdb.connect(str(tmp_path / 'e.duckdb'))
    with pytest.raises(RuntimeError, match='Missing tables'):
        connection.require_tables(empty)


def test_connection_is_read_only(synthetic_db):
    """Analysis connections can't write."""
    c = connection.get_connection(str(synthetic_db))
    with pytest.raises(duckdb.Error):
        c.execute("CREATE TABLE x (a INT)")


def test_build_claims_view_from_parquet(tmp_path):
    """build_claims_table creates a view over YYYY__*.parquet with year taken from the file name."""
    pq = tmp_path / 'pq'
    pq.mkdir()
    c = duckdb.connect(str(tmp_path / 'db.duckdb'))
    for y in (2018, 2019):
        c.execute(f"COPY (SELECT * FROM (VALUES ('1', 1.0), ('2', 2.0)) t(Rndrng_NPI, Tot_Srvcs)) "
                  f"TO '{pq / f'{y}__claims_{y}.parquet'}' (FORMAT parquet)")
    build.build_claims_table(c, pq)
    assert c.execute(f"SELECT year, COUNT(*) FROM {config.CLAIMS_TABLE} GROUP BY year ORDER BY year").fetchall() == [(2018, 2), (2019, 2)]
    kind = c.execute(f"SELECT table_type FROM information_schema.tables WHERE table_name='{config.CLAIMS_TABLE}'").fetchall()[0][0]
    assert kind == 'VIEW'
    build.build_claims_table(c, pq, materialize=True)
    kind = c.execute(f"SELECT table_type FROM information_schema.tables WHERE table_name='{config.CLAIMS_TABLE}'").fetchall()[0][0]
    assert kind == 'BASE TABLE'


def test_build_claims_without_parquet_fails(tmp_path):
    """A clear error when no Parquet files exist."""
    with pytest.raises(FileNotFoundError):
        build.build_claims_table(duckdb.connect(), tmp_path)


def test_load_gv_puf_keeps_all_columns_as_text(tmp_path):
    """The GV PUF is stored raw, every column VARCHAR."""
    f = tmp_path / 'gv.csv'
    f.write_text('YEAR,BENE_AVG_AGE,OTHER\n2023,72.1,5\n')
    c = duckdb.connect()
    build.load_gv_puf(c, str(f))
    assert {r[1] for r in c.execute(f"DESCRIBE {config.GV_TABLE}").fetchall()} == {'VARCHAR'}
    with pytest.raises(FileNotFoundError):
        build.load_gv_puf(c, str(tmp_path / 'missing*.csv'))
