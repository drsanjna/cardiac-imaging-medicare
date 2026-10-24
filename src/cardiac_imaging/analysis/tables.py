"""Table 1: provider specialty distribution by modality — also the source of the forest-plot share labels."""
from .. import config
from ..style import PROC_ORDER


def specialty_distribution(con, year=config.END_YEAR):
    """Cardiology / Radiology / Other % of services and total volume, per modality."""
    t1 = con.execute(f"""
        SELECT {config.MODALITY_CASE} AS modality,
            CASE
                WHEN Rndrng_Prvdr_Type IN {config.RAD_TYPES}  THEN 'Radiology'
                WHEN Rndrng_Prvdr_Type IN {config.CARD_TYPES} THEN 'Cardiology'
                ELSE 'Other'
            END AS spec_group,
            SUM(Tot_Srvcs) AS total_services
        FROM {config.CLAIMS_TABLE}
        WHERE year = {year} AND Rndrng_Prvdr_Cntry = 'US'
          {config.EXCL_SQL}
          AND ({config.MODALITY_CASE}) IS NOT NULL
        GROUP BY modality, spec_group
    """).fetchdf()
    t1p = t1.pivot_table(index='modality', columns='spec_group',
                         values='total_services', aggfunc='sum').fillna(0)
    for c in ['Cardiology', 'Radiology', 'Other']:
        if c not in t1p.columns:
            t1p[c] = 0
    t1p['Total Volume'] = t1p[['Cardiology', 'Radiology', 'Other']].sum(axis=1)
    for c in ['Cardiology', 'Radiology', 'Other']:
        t1p[c + ' %'] = t1p[c] / t1p['Total Volume'] * 100
    t1p = t1p.reindex(PROC_ORDER)
    table1 = t1p[['Cardiology %', 'Radiology %', 'Other %', 'Total Volume']].copy()
    table1.columns.name = None

    print("\n" + "=" * 78)
    print(f"TABLE 1 — Provider specialty distribution by modality, {year} (final)")
    print("=" * 78)
    print(table1.round(1).to_string(
        formatters={'Total Volume': lambda v: f"{int(v):,}"}))
    return table1


def cta_shares(table1):
    """(radiology %, cardiology %) of CTA interpretations, straight from Table 1's CTA row."""
    cta_row = table1.loc['Cardiac CTA']
    share_rad, share_card = cta_row['Radiology %'], cta_row['Cardiology %']
    print(f"\nForest-plot annotations from Table 1: "
          f"Radiology {share_rad:.1f}% | Cardiology {share_card:.1f}%")
    return share_rad, share_card
