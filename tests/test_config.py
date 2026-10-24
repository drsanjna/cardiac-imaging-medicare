"""Invariants of the single source of truth (config.py) and the figure catalog."""
import importlib
import re

from cardiac_imaging import config
from cardiac_imaging.figures import catalog


def test_population_rules():
    """Territories and invalid codes are excluded; specialty groups don't overlap."""
    assert set(config.TERR) <= set(config.EXCLUDED_AREAS)
    assert {'XX', 'ZZ', ''} <= set(config.EXCLUDED_AREAS)
    assert not set(config.RAD_TYPES) & set(config.CARD_TYPES)
    assert "NOT IN" in config.EXCL_SQL and "Rndrng_Prvdr_State_Abrvtn" in config.EXCL_SQL


def test_geography_lookups_cover_50_states_plus_dc():
    """Name and FIPS lookups agree on the same 51 jurisdictions."""
    abbrs = set(config.STATE_ABBR_MAP.values())
    assert len(abbrs) == 51 and 'DC' in abbrs and not abbrs & set(config.TERR)
    assert set(config.FIPS2ABBR.values()) == abbrs
    assert all(len(k) == 2 and k.isdigit() for k in config.FIPS2ABBR)


def test_study_window_and_enrollment():
    """National enrollment exists for every study year."""
    assert config.BASE_YEAR < config.END_YEAR
    assert set(range(config.BASE_YEAR, config.END_YEAR + 1)) <= set(config.MEDICARE_ENROLLMENT)
    assert all(v > 1_000_000 for v in config.MEDICARE_ENROLLMENT.values())


def test_modality_sql_maps_every_cardiac_code():
    """Every code in the HCPCS filter is assigned a modality and a modality type."""
    codes = set(re.findall(r"'(\d{5})'", config.CARDIAC_HCPCS_WHERE))
    for code in codes:
        assert code in config.MODALITY_CASE or '75557' <= code <= '75565'
        assert code in config.MODALITY_TYPE_CASE or '75557' <= code <= '75565'
    assert config.CTA_CODE in codes


def test_relative_env_paths_resolve_inside_repo(monkeypatch):
    """CARDIAC_* relative paths are resolved against the repo root."""
    monkeypatch.setenv('CARDIAC_OUTPUT_DIR', 'some/out')
    fresh = importlib.reload(config)
    try:
        assert fresh.OUTPUT_DIR == fresh.REPO_ROOT / 'some' / 'out'
    finally:
        monkeypatch.delenv('CARDIAC_OUTPUT_DIR')
        importlib.reload(config)


def test_catalog_entries_are_complete_and_unique():
    """Every figure has a unique stem, a known section, and code + table references."""
    stems = [f['stem'] for f in catalog.FIGURES]
    assert len(stems) == len(set(stems)) == 12
    for f in catalog.FIGURES:
        assert f['section'] in catalog.SECTIONS
        assert f['title'] and f['caption'] and f['label']
        assert f['sources'] and f['tables']


def test_catalog_sources_point_at_real_functions():
    """Each 'module:function' in the catalog exists (so chart discussions load real code)."""
    for f in catalog.FIGURES:
        for ref in f['sources']:
            module, func = ref.split(':')
            mod = importlib.import_module(f'cardiac_imaging.{module}')
            assert callable(getattr(mod, func, None)), ref
