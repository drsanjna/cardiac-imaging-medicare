"""CTA-billing physician density by state (all / radiology / cardiology) and national NPI counts, 2023."""
from .. import config
from ..audit import log_filter

_CTA_WHERE = (f"year={config.END_YEAR} AND HCPCS_Cd='{config.CTA_CODE}' "
              f"AND Rndrng_Prvdr_Cntry='US' {config.EXCL_SQL}")


def _specialty_npis(con, types, count_col):
    df = con.execute(f"""
        SELECT Rndrng_NPI, Rndrng_Prvdr_State_Abrvtn AS state
        FROM {config.CLAIMS_TABLE} WHERE {_CTA_WHERE} AND Rndrng_Prvdr_Type IN {types}
        GROUP BY Rndrng_NPI, state
    """).fetchdf()
    return df.groupby('state').agg(**{count_col: ('Rndrng_NPI', 'nunique')}).reset_index()


def _with_enrollment(df, state_ffs, label):
    df['ffs_enrollment'] = df['state'].map(state_ffs)
    kept = df.dropna(subset=['ffs_enrollment'])
    log_filter(f'{label}: states with FFS enrollment', len(df), len(kept), unit='states',
               dropped_items=set(df['state']) - set(kept['state']))
    return kept


def _specialty_frame(vol, npis, count_col, density_col, state_ffs, demo, label):
    df = vol.merge(npis, on='state', how='left')
    df[count_col] = df[count_col].fillna(0).astype(int)
    df = _with_enrollment(df, state_ffs, label)
    df['rate_per_1000'] = df['total_services'] / df['ffs_enrollment'] * 1_000
    df[density_col]     = df[count_col]        / df['ffs_enrollment'] * 100_000
    kept = df[df[count_col] > 0]
    log_filter(f'{label}: states with ≥1 specialty CTA biller', len(df), len(kept), unit='states',
               dropped_items=set(df['state']) - set(kept['state']))
    return kept.merge(demo, on='state', how='left')


def load_cta_density_frames(con, state_ffs, demo):
    """State-level CTA volume + NPI density + demographics, keyed 'all', 'rad', 'card'."""
    _all = con.execute(f"""
        SELECT Rndrng_NPI, Rndrng_Prvdr_State_Abrvtn AS state, SUM(Tot_Srvcs) AS total_services
        FROM {config.CLAIMS_TABLE} WHERE {_CTA_WHERE} GROUP BY Rndrng_NPI, state
    """).fetchdf()
    vol = (_all.groupby('state').agg(total_services=('total_services', 'sum'),
           total_unique_npis=('Rndrng_NPI', 'nunique')).reset_index())

    df_all = (_all.groupby('state').agg(total_services=('total_services', 'sum'),
              unique_npis=('Rndrng_NPI', 'nunique')).reset_index())
    df_all = _with_enrollment(df_all, state_ffs, 'all providers')
    df_all['rate_per_1000'] = df_all['total_services'] / df_all['ffs_enrollment'] * 1_000
    df_all['npis_per_100k'] = df_all['unique_npis']    / df_all['ffs_enrollment'] * 100_000
    df_all = df_all.merge(demo, on='state', how='left')

    df_rad = _specialty_frame(vol, _specialty_npis(con, config.RAD_TYPES, 'rad_unique_npis'),
                              'rad_unique_npis', 'rad_npis_per_100k', state_ffs, demo, 'radiologists')
    df_card = _specialty_frame(vol, _specialty_npis(con, config.CARD_TYPES, 'card_unique_npis'),
                               'card_unique_npis', 'card_npis_per_100k', state_ffs, demo, 'cardiologists')
    return {'all': df_all, 'rad': df_rad, 'card': df_card}


def national_physician_counts(con):
    """COUNT(DISTINCT NPI) across all states combined — multi-state billers counted once."""
    def count(extra=''):
        return con.execute(
            f"SELECT COUNT(DISTINCT Rndrng_NPI) FROM {config.CLAIMS_TABLE} WHERE {_CTA_WHERE} {extra}"
        ).fetchall()[0][0]
    counts = {
        'all':  count(),
        'rad':  count(f"AND Rndrng_Prvdr_Type IN {config.RAD_TYPES}"),
        'card': count(f"AND Rndrng_Prvdr_Type IN {config.CARD_TYPES}"),
    }
    print(f"National unique CTA-billing NPIs, {config.END_YEAR}: "
          f"All={counts['all']:,} | Radiologists={counts['rad']:,} | "
          f"Cardiologists={counts['card']:,}")
    return counts


def report_states_without_billers(state_ffs, frames):
    """Print which of the 50 states + DC had zero CTA billers of each specialty."""
    all_50_dc = set(state_ffs.keys()) - set(config.TERR)
    missing = {k: sorted(all_50_dc - set(frames[k]['state'])) for k in ('all', 'rad', 'card')}
    print("\n" + "=" * 76)
    print(f"STATES WITH ZERO CTA-BILLING PHYSICIANS BY SPECIALTY ({config.END_YEAR})")
    print("=" * 76)
    print(f"No CTA billers of ANY specialty ({len(missing['all'])}): "
          f"{missing['all'] if missing['all'] else 'none'}")
    print(f"No radiologist CTA billers      ({len(missing['rad'])}): "
          f"{missing['rad'] if missing['rad'] else 'none'}")
    print(f"No cardiologist CTA billers     ({len(missing['card'])}): "
          f"{missing['card'] if missing['card'] else 'none'}")
    print("=" * 76 + "\n")
    return missing
