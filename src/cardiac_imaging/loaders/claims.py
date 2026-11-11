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


def load_comparator_detail(con, label, codes):
    """Rows for one comparator procedure (e.g. ICA, TAVR), labelled `label` (territories excluded, logged)."""
    where = f"HCPCS_Cd IN {tuple(codes)}"
    query = f"""
    SELECT year, Rndrng_NPI, HCPCS_Cd,
        '{label}' AS procedure_category,
        Place_Of_Srvc AS place_of_service,
        Rndrng_Prvdr_State_Abrvtn AS state,
        Tot_Srvcs
    FROM {config.CLAIMS_TABLE}
    WHERE {where}
      {config.EXCL_SQL}
    """
    n_all = con.execute(f"SELECT COUNT(*) FROM {config.CLAIMS_TABLE} WHERE {where}").fetchall()[0][0]
    df = con.execute(query).fetchdf()
    log_filter(f'{label} rows, excluding territories/invalid states', n_all, len(df))
    print(f"{label} loaded: {len(df):,} rows ({codes[0]}–{codes[-1]})")
    return df


COMPARATOR_COLUMNS = ['year', 'Rndrng_NPI', 'HCPCS_Cd', 'procedure_category', 'place_of_service', 'state', 'Tot_Srvcs']


def load_comparators(con, comparators=None):
    """All comparator procedures (default config.COMPARATORS), one frame; an empty frame when they are switched off."""
    import pandas as pd
    comparators = config.COMPARATORS if comparators is None else comparators
    if not comparators:
        print("Comparators (ICA, TAVR, CACS) switched off (config.INCLUDE_COMPARATORS).")
        return pd.DataFrame(columns=COMPARATOR_COLUMNS)
    return pd.concat([load_comparator_detail(con, label, codes) for label, codes in comparators.items()],
                     ignore_index=True)


def comparator_trend(df_comp):
    """Total comparator services by year × procedure, in the national_trend format (empty in, empty out)."""
    import pandas as pd
    if df_comp.empty:
        return pd.DataFrame(columns=['year', 'procedure_category', 'total_services'])
    return (df_comp.groupby(['year', 'procedure_category'])['Tot_Srvcs'].sum()
            .rename('total_services').reset_index())


SURGERY_TYPES = ('Thoracic Surgery', 'Cardiac Surgery', 'Vascular Surgery', 'General Surgery')   # General Surgery: ~1,200 TAVR services/yr (2024), surgeons enrolled under the generic code


def tavr_cosurgeon_split(con):
    """TAVR services by year billed by cardiology, by cardiac/thoracic/vascular surgery and by everyone else, with the
    cardiology:surgery ratio (≈1 when every procedure is co-billed) and the implied procedure count (services ÷ 2)."""
    import pandas as pd
    df = con.execute(f"""
    SELECT year,
        CASE WHEN Rndrng_Prvdr_Type IN {config.CARD_TYPES} THEN 'cardiology'
             WHEN Rndrng_Prvdr_Type IN {SURGERY_TYPES}     THEN 'surgery'
             ELSE 'other' END AS billing_group,
        SUM(Tot_Srvcs) AS services
    FROM {config.CLAIMS_TABLE}
    WHERE HCPCS_Cd IN {config.TAVR_CODES}
      {config.EXCL_SQL}
    GROUP BY 1, 2
    """).fetchdf()
    wide = (df.pivot(index='year', columns='billing_group', values='services')
            .reindex(columns=['cardiology', 'surgery', 'other']).fillna(0.0).sort_index())
    wide['total_services'] = wide.sum(axis=1)
    wide['cardiology_to_surgery_ratio'] = wide['cardiology'] / wide['surgery'].replace(0, pd.NA)
    wide['procedures_est'] = wide['total_services'] / config.TAVR_SERVICES_PER_PROCEDURE
    wide.columns.name = None
    return wide.reset_index()


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
