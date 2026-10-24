"""Utilization rates per 1,000 FFS beneficiaries: national decomposition, market share, state rates and deltas."""
import pandas as pd

from .. import config
from ..audit import log_filter
from ..style import FIG1_ORDER, PROC_ORDER

SEGMENTS = ['Urban / Office', 'Urban / Facility', 'Rural / Office', 'Rural / Facility']


def decompose(trend):
    """Add national FFS enrollment and rate per 1,000 to the year × modality trend (Figure 1 data)."""
    decomp_df = trend.copy()
    decomp_df['enrollment'] = decomp_df['year'].map(config.MEDICARE_ENROLLMENT)
    decomp_df['rate_per_1000'] = decomp_df['total_services'] / decomp_df['enrollment'] * 1000
    return decomp_df


def change_summary(decomp_df, y0=config.BASE_YEAR, y1=config.END_YEAR, procs=None):
    """% change in volume, national FFS enrollment and rate between y0 and y1, one row per modality (or `procs`)."""
    enr = config.MEDICARE_ENROLLMENT
    enr_chg = (enr[y1] - enr[y0]) / enr[y0] * 100
    rows = []
    for proc in procs or [p for p in FIG1_ORDER if p in set(decomp_df['procedure_category'])]:
        sub = decomp_df[decomp_df['procedure_category'] == proc]
        v0 = sub.loc[sub['year'] == y0, 'total_services'].values[0]
        v1 = sub.loc[sub['year'] == y1, 'total_services'].values[0]
        r0 = sub.loc[sub['year'] == y0, 'rate_per_1000'].values[0]
        r1 = sub.loc[sub['year'] == y1, 'rate_per_1000'].values[0]
        rows.append(dict(modality=proc, volume_pct=(v1 - v0) / v0 * 100, enrollment_pct=enr_chg,
                         rate_pct=(r1 - r0) / r0 * 100))
    return pd.DataFrame(rows).set_index('modality')


def print_change_summary(decomp_df, y0=config.BASE_YEAR, y1=config.END_YEAR):
    """Print volume / enrollment / rate % change between y0 and y1 for each modality."""
    print(f"\n  {y0} → {y1} Change Summary:")
    print(f"  {'Modality':<15} {'Volume Δ%':>12} {'Enrollment Δ%':>15} {'Rate Δ%':>12}")
    for proc, r in change_summary(decomp_df, y0, y1).iterrows():
        print(f"  {proc:<15} {r.volume_pct:>+11.1f}% {r.enrollment_pct:>+14.1f}% {r.rate_pct:>+11.1f}%")


def market_share_by_segment(df_agg):
    """{segment: year × modality % share} for the four rural/urban × office/facility segments (Figure 2 data)."""
    market_data = {}
    for seg in SEGMENTS:
        seg_pivot = df_agg[df_agg['segment'] == seg].pivot_table(
            index='year', columns='procedure_category', values='total_services', aggfunc='sum'
        ).reindex(columns=PROC_ORDER).fillna(0)
        market_data[seg] = seg_pivot.div(seg_pivot.sum(axis=1), axis=0) * 100
    return market_data


def national_market_share(trend):
    """Year × modality % share nationally, plus Traditional and Advanced totals."""
    nat_pivot = trend.pivot_table(index='year', columns='procedure_category',
                                  values='total_services', aggfunc='sum'
                                  ).reindex(columns=PROC_ORDER).fillna(0)
    nat_pct = nat_pivot.div(nat_pivot.sum(axis=1), axis=0) * 100
    nat_pct['Traditional'] = nat_pct['Echo'] + nat_pct['SPECT']
    nat_pct['Advanced'] = nat_pct['Cardiac CTA'] + nat_pct['Cardiac MRI'] + nat_pct['Cardiac PET']
    return nat_pct


def compute_state_rates(df_detail_sub, state_ffs_lookup):
    """State × modality services and rate per 1,000 FFS beneficiaries."""
    sp = (df_detail_sub.groupby(['state', 'procedure_category'])
          .agg(total_services=('Tot_Srvcs', 'sum')).reset_index())
    sp['ffs_enrollment'] = sp['state'].map(state_ffs_lookup)
    n, states = len(sp), set(sp['state'])
    sp = sp.dropna(subset=['ffs_enrollment'])
    sp = sp[sp['ffs_enrollment'] > 0]
    log_filter('state × modality rows with FFS enrollment', n, len(sp),
               dropped_items=states - set(sp['state']))
    sp['rate_per_1000'] = sp['total_services'] / sp['ffs_enrollment'] * 1000
    return sp


def rate_deltas(rates_end, rates_base, missing_as_zero=True):
    """Outer-join end-year and base-year state rates; rate_delta = end − base.

    missing_as_zero=False keeps a state with no rows in one year as missing (no delta) instead of treating it as 0 —
    for procedures where an absent state means suppressed or no program, not zero use.
    """
    delta_df = rates_end[['state', 'procedure_category', 'rate_per_1000']].merge(
        rates_base[['state', 'procedure_category', 'rate_per_1000']],
        on=['state', 'procedure_category'], suffixes=('_2023', '_2018'), how='outer'
    )
    if missing_as_zero:
        delta_df = delta_df.fillna(0)
    delta_df['rate_delta'] = delta_df['rate_per_1000_2023'] - delta_df['rate_per_1000_2018']
    return delta_df


def state_summary_table(state_rates):
    """State × modality rate table with an 'All Cardiac' total, sorted descending."""
    summary_pivot = (state_rates.pivot_table(
        index='state', columns='procedure_category',
        values='rate_per_1000', aggfunc='sum'
    ).reindex(columns=PROC_ORDER).fillna(0).round(2))
    summary_pivot['All Cardiac'] = summary_pivot.sum(axis=1)
    return summary_pivot.sort_values('All Cardiac', ascending=False)
