"""Claims-level cardiac imaging data: specialty guard, procedure-level detail, segment aggregates."""
from .. import config
from ..audit import log_filter


def verify_specialty_strings(con):
    """Every specialty string must exist verbatim in the PUF."""
    types = set(con.execute(
        f"SELECT DISTINCT Rndrng_Prvdr_Type FROM {config.CLAIMS_TABLE}"
    ).fetchdf()['Rndrng_Prvdr_Type'].dropna())
    for s in config.RAD_TYPES + config.CARD_TYPES:
        assert s in types, f"Specialty string not found in PUF: {s!r}"
    print(f"Specialty-string guard passed ({len(config.RAD_TYPES + config.CARD_TYPES)} strings verified).")


def load_detail(con):
    """One row per provider × HCPCS × year for the 5 cardiac modalities (territories excluded)."""
    # RUCA is stored as VARCHAR in Parquet; TRY_CAST reproduces the numeric comparison of the CSV-era code.
    query = f"""
    SELECT year, Rndrng_NPI, HCPCS_Cd,
        {config.MODALITY_CASE} AS procedure_category,
        {config.MODALITY_TYPE_CASE} AS modality_type,
        CASE
            WHEN TRY_CAST(Rndrng_Prvdr_RUCA AS DOUBLE) <= 3.0 THEN 'Urban'
            WHEN TRY_CAST(Rndrng_Prvdr_RUCA AS DOUBLE) > 3.0  THEN 'Rural'
            ELSE 'Unknown'
        END AS rural_urban,
        Place_Of_Srvc AS place_of_service,
        Rndrng_Prvdr_State_Abrvtn AS state,
        Tot_Srvcs,
        Tot_Bene_Day_Srvcs
    FROM {config.CLAIMS_TABLE}
    WHERE {config.CARDIAC_HCPCS_WHERE}
      {config.EXCL_SQL}
    """
    n_cardiac = con.execute(
        f"SELECT COUNT(*) FROM {config.CLAIMS_TABLE} WHERE {config.CARDIAC_HCPCS_WHERE}").fetchall()[0][0]
    df_detail = con.execute(query).fetchdf()
    log_filter('cardiac HCPCS rows, excluding territories/invalid states', n_cardiac, len(df_detail))
    n = len(df_detail)
    df_detail = df_detail[df_detail['procedure_category'].notna()].copy()
    log_filter('rows with a modality assigned', n, len(df_detail))
    print(f"Data loaded: {len(df_detail):,} rows, {df_detail['year'].nunique()} years")
    print(f"States: {df_detail['state'].nunique()} (territories & invalid codes excluded)")
    return df_detail


def aggregate_segments(df_detail):
    """Services and unique NPIs by year × modality × rural/urban × place of service (Unknown RUCA dropped)."""
    df_agg = (df_detail.groupby(['year', 'procedure_category', 'rural_urban', 'place_of_service'])
              .agg(total_services=('Tot_Srvcs', 'sum'),
                   unique_npis=('Rndrng_NPI', 'nunique'))
              .reset_index())
    df_agg['segment'] = df_agg['rural_urban'] + ' / ' + df_agg['place_of_service'].map({'F': 'Facility', 'O': 'Office'})
    kept = df_agg[df_agg['rural_urban'] != 'Unknown']
    log_filter('services with known RUCA (segment analyses)',
               int(df_agg['total_services'].sum()), int(kept['total_services'].sum()), unit='services')
    return kept


def national_trend(df_agg):
    """Total services by year × modality."""
    return df_agg.groupby(['year', 'procedure_category'])['total_services'].sum().reset_index()
