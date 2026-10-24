import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.gridspec as gridspec
from matplotlib.lines import Line2D
from scipy import stats

# ==========================================================================
# MASTER CONFIGURATION — publication typography (JACC: optimal 12 pt, min 10 pt)
# ==========================================================================
plt.rcParams['figure.dpi'] = 150
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 12          # base lettering 12 pt
plt.rcParams['axes.titlesize'] = 13
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['xtick.labelsize'] = 10    # never below 10 pt
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10

# TIFF export settings (JACC: color/grayscale >=300 DPI, line art >=1200 DPI)
TIFF_LINEART_DPI = 1200   # single-panel matplotlib line art
TIFF_PANEL_DPI   = 600    # large multi-panel line art (1200 makes >20k-px files;
                          # raise to 1200 for final submission if files are manageable)
TIFF_RASTER_DPI  = 300    # plotly choropleths (raster)

def save_pub_fig(fig, stem, tiff_dpi):
    """Save a matplotlib figure as working PNG (300 DPI) + submission TIFF (LZW)."""
    fig.savefig(f'{stem}.png', bbox_inches='tight', dpi=300)
    try:
        fig.savefig(f'{stem}.tiff', bbox_inches='tight', dpi=tiff_dpi,
                    pil_kwargs={'compression': 'tiff_lzw'})
        print(f"  Saved: {stem}.png (300 DPI) and {stem}.tiff ({tiff_dpi} DPI)")
    except Exception as e:
        print(f"  Saved: {stem}.png (300 DPI); TIFF failed ({e}) — install pillow")

def png_to_tiff(png_path, dpi=TIFF_RASTER_DPI):
    """Convert a plotly PNG export to TIFF with DPI metadata."""
    try:
        from PIL import Image
        tiff_path = png_path.rsplit('.', 1)[0] + '.tiff'
        Image.open(png_path).save(tiff_path, dpi=(dpi, dpi), compression='tiff_lzw')
        print(f"  Converted: {tiff_path} ({dpi} DPI)")
    except Exception as e:
        print(f"  TIFF conversion failed for {png_path}: {e}")

con = duckdb.connect()

con.execute("""
    CREATE OR REPLACE VIEW medicare AS
    SELECT *,
        CAST(regexp_extract(filename, '(\\d{4})\\.csv', 1) AS INTEGER) AS year
    FROM read_csv_auto(
        '/Users/sanjnapatel/Downloads/Data/Medicare_Physician_Other_Practitioners_by_Provider_and_Service_*.csv',
        filename=true,
        ignore_errors=true
    )
""")

# ==========================================================================
# ANALYTIC POPULATION & SPECIALTY DEFINITIONS — single source of truth
# 50 states + DC only. Excluded everywhere: American Samoa, Guam, Northern
# Mariana Islands, Puerto Rico, US Virgin Islands, and unknown/invalid codes.
# ==========================================================================
EXCLUDED_AREAS = ('AS', 'GU', 'MP', 'PR', 'VI', 'XX', 'ZZ', '')
EXCL_SQL = f"AND Rndrng_Prvdr_State_Abrvtn NOT IN {EXCLUDED_AREAS}"

RAD_TYPES  = ('Diagnostic Radiology', 'Nuclear Medicine', 'Interventional Radiology')
CARD_TYPES = ('Cardiology', 'Interventional Cardiology',
              'Clinical Cardiac Electrophysiology',
              'Advanced Heart Failure and Transplant Cardiology')

# --- GUARD: every specialty string must exist verbatim in the PUF. ---------
_types = set(con.execute(
    "SELECT DISTINCT Rndrng_Prvdr_Type FROM medicare"
).fetchdf()['Rndrng_Prvdr_Type'].dropna())
for s in RAD_TYPES + CARD_TYPES:
    assert s in _types, f"Specialty string not found in PUF: {s!r}"
print(f"Specialty-string guard passed ({len(RAD_TYPES + CARD_TYPES)} strings verified).")

MODALITY_CASE = """
    CASE
        WHEN HCPCS_Cd BETWEEN '75557' AND '75565' THEN 'Cardiac MRI'
        WHEN HCPCS_Cd = '75574'                    THEN 'Cardiac CTA'
        WHEN HCPCS_Cd IN ('78491','78492')          THEN 'Cardiac PET'
        WHEN HCPCS_Cd IN ('93306','93307','93308')  THEN 'Echo'
        WHEN HCPCS_Cd IN ('78451','78452')          THEN 'SPECT'
    END
"""

# ==========================================================================
# ENROLLMENT: CMS Program Statistics — Original Medicare Enrollment
# ==========================================================================
MEDICARE_ENROLLMENT = {
    2018: 37_994_241, 2019: 37_898_471, 2020: 37_094_414,
    2021: 35_681_342, 2022: 34_596_702, 2023: 33_694_472,
}

# ==========================================================================
# COLOR PALETTE
# ==========================================================================
COLOR_ECHO  = '#7B8FA1'
COLOR_SPECT = '#A8BED1'
COLOR_CTA   = '#8B3A8B'
COLOR_MRI   = '#C154C1'
COLOR_PET   = '#E88BE8'

PROC_ORDER  = ['Echo', 'SPECT', 'Cardiac CTA', 'Cardiac MRI', 'Cardiac PET']
PROC_COLORS = [COLOR_ECHO, COLOR_SPECT, COLOR_CTA, COLOR_MRI, COLOR_PET]

COLOR_VOLUME     = '#C0392B'
COLOR_ENROLLMENT = '#7F8C8D'
COLOR_RATE       = '#2471A3'

PURPLE_SCALE = [
    [0.0,  '#f2e6f7'], [0.15, '#e0c7ee'], [0.3,  '#cc9edf'],
    [0.45, '#b676d0'], [0.6,  '#9b4dba'], [0.75, '#7e2ea0'],
    [0.9,  '#5e1580'], [1.0,  '#3b0062'],
]
DELTA_SCALE = [
    [0.0,  '#b2182b'], [0.25, '#ef8a62'], [0.5,  '#f7f7f7'],
    [0.75, '#67a9cf'], [1.0,  '#2166ac'],
]

# ==========================================================================
# DATA PIPELINE
# ==========================================================================
print("=" * 80)
print("LOADING AND PROCESSING DATA")
print("=" * 80)

QUERY_DETAIL = f"""
SELECT year, Rndrng_NPI, HCPCS_Cd,
    {MODALITY_CASE} AS procedure_category,
    CASE
        WHEN HCPCS_Cd BETWEEN '75557' AND '75565' THEN 'Advanced'
        WHEN HCPCS_Cd = '75574'                    THEN 'Advanced'
        WHEN HCPCS_Cd IN ('78491','78492')          THEN 'Advanced'
        WHEN HCPCS_Cd IN ('93306','93307','93308')  THEN 'Traditional'
        WHEN HCPCS_Cd IN ('78451','78452')          THEN 'Traditional'
    END AS modality_type,
    CASE
        WHEN Rndrng_Prvdr_RUCA <= 3.0 THEN 'Urban'
        WHEN Rndrng_Prvdr_RUCA > 3.0  THEN 'Rural'
        ELSE 'Unknown'
    END AS rural_urban,
    Place_Of_Srvc AS place_of_service,
    Rndrng_Prvdr_State_Abrvtn AS state,
    Tot_Srvcs,
    Tot_Bene_Day_Srvcs
FROM medicare
WHERE (HCPCS_Cd BETWEEN '75557' AND '75565'
   OR HCPCS_Cd = '75574'
   OR HCPCS_Cd IN ('78491','78492')
   OR HCPCS_Cd IN ('93306','93307','93308')
   OR HCPCS_Cd IN ('78451','78452'))
  {EXCL_SQL}
"""

df_detail = con.execute(QUERY_DETAIL).fetchdf()
df_detail = df_detail[df_detail['procedure_category'].notna()].copy()

df_agg = (df_detail.groupby(['year', 'procedure_category', 'rural_urban', 'place_of_service'])
          .agg(total_services=('Tot_Srvcs', 'sum'),
               unique_npis=('Rndrng_NPI', 'nunique'))
          .reset_index())
df_agg['segment'] = df_agg['rural_urban'] + ' / ' + df_agg['place_of_service'].map({'F': 'Facility', 'O': 'Office'})
df_agg = df_agg[df_agg['rural_urban'] != 'Unknown']

trend = df_agg.groupby(['year', 'procedure_category'])['total_services'].sum().reset_index()

print(f"Data loaded: {len(df_detail):,} rows, {df_detail['year'].nunique()} years")
print(f"States: {df_detail['state'].nunique()} (territories & invalid codes excluded)")
print("Data pipeline complete.\n")


# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 1: Volume / Enrollment / Rate Decomposition (3×5 panels)
# ══════════════════════════════════════════════════════════════════════════
print("Building Figure 1: Volume/Enrollment/Rate Decomposition...")

fig = plt.figure(figsize=(22, 13))
outer_gs = gridspec.GridSpec(3, 5, hspace=0.45, wspace=0.35,
                             left=0.05, right=0.97, top=0.87, bottom=0.07)

decomp_df = trend.copy()
decomp_df['enrollment'] = decomp_df['year'].map(MEDICARE_ENROLLMENT)
decomp_df['rate_per_1000'] = decomp_df['total_services'] / decomp_df['enrollment'] * 1000
years_all = sorted(decomp_df['year'].unique())

ROW_CONFIG = [
    ('total_services', 'Procedure Volume',             COLOR_VOLUME,     'o'),
    ('enrollment',     'FFS Enrollment',                COLOR_ENROLLMENT, 's'),
    ('rate_per_1000',  'Rate per 1,000 Beneficiaries',  COLOR_RATE,       'D'),
]

for col_idx, proc in enumerate(PROC_ORDER):
    sub = decomp_df[decomp_df['procedure_category'] == proc].sort_values('year')
    years = sub['year'].values
    for row_idx, (col_name, row_label, color, marker) in enumerate(ROW_CONFIG):
        ax = fig.add_subplot(outer_gs[row_idx, col_idx])
        vals = sub[col_name].values
        ax.plot(years, vals, marker=marker, color=color, linewidth=2.2, markersize=7, zorder=3)
        ax.fill_between(years, vals, alpha=0.08, color=color, zorder=1)
        for yr, v in zip(years, vals):
            if col_name == 'enrollment':
                label = f'{v/1e6:.1f}M'
            elif col_name == 'total_services':
                label = f'{v/1e6:.2f}M' if v >= 1_000_000 else f'{v/1e3:.1f}K'
            else:
                label = f'{v:.2f}'
            ax.annotate(label, (yr, v), textcoords="offset points", xytext=(0, 9),
                        fontsize=10, ha='center', color=color, fontweight='bold')
        ax.set_xticks(years_all)
        ax.tick_params(labelsize=10)
        ax.grid(True, alpha=0.2)
        if col_name == 'enrollment':
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e6:.0f}M'))
        elif col_name == 'total_services':
            if vals.max() >= 1_000_000:
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e6:.1f}M'))
            else:
                ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x/1e3:.0f}K'))
        ymin, ymax = vals.min(), vals.max()
        yrange = ymax - ymin if ymax != ymin else ymax * 0.1
        ax.set_ylim(ymin - yrange * 0.15, ymax + yrange * 0.3)
        if row_idx == 0:
            ax.set_title(proc, fontsize=13, fontweight='bold', pad=10)
        if col_idx == 0:
            ax.set_ylabel(row_label, fontsize=11, fontweight='bold')
        if row_idx == 2:
            ax.set_xlabel('Year', fontsize=11)
        else:
            ax.set_xticklabels([])

fig.suptitle('Figure 1. Decomposing Procedure Volume: Volume vs. FFS Enrollment vs. Utilization Rate\n'
             'Source: CMS Medicare Physician & Other Practitioners  |  Denominator: CMS Original Medicare Enrollment',
             fontsize=14, fontweight='bold', y=0.96)
fig.text(0.05, 0.015,
         'Symbols: circles = annual procedure volume; squares = national FFS enrollment; '
         'diamonds = utilization rate per 1,000 FFS beneficiaries.',
         fontsize=10, color='#555555')
save_pub_fig(fig, 'figure1_decomposition', TIFF_PANEL_DPI)
plt.show()
plt.close()

print("\n  2018 → 2023 Change Summary:")
print(f"  {'Modality':<15} {'Volume Δ%':>12} {'Enrollment Δ%':>15} {'Rate Δ%':>12}")
enr_chg = (MEDICARE_ENROLLMENT[2023] - MEDICARE_ENROLLMENT[2018]) / MEDICARE_ENROLLMENT[2018] * 100
for proc in PROC_ORDER:
    sub = decomp_df[decomp_df['procedure_category'] == proc]
    v18 = sub.loc[sub['year'] == 2018, 'total_services'].values[0]
    v23 = sub.loc[sub['year'] == 2023, 'total_services'].values[0]
    r18 = sub.loc[sub['year'] == 2018, 'rate_per_1000'].values[0]
    r23 = sub.loc[sub['year'] == 2023, 'rate_per_1000'].values[0]
    print(f"  {proc:<15} {(v23-v18)/v18*100:>+11.1f}% {enr_chg:>+14.1f}% {(r23-r18)/r18*100:>+11.1f}%")
print("Figure 1 complete.\n")


# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 2: Market Share — Stacked Area with Advanced Zoom Insets
# ══════════════════════════════════════════════════════════════════════════
print("Building Figure 2: Market Share...")

segments_for_chart = ['Urban / Office', 'Urban / Facility', 'Rural / Office', 'Rural / Facility']
seg_titles = {
    'Urban / Office': 'Urban – Office', 'Urban / Facility': 'Urban – Facility',
    'Rural / Office': 'Rural – Office', 'Rural / Facility': 'Rural – Facility',
}

market_data = {}
for seg in segments_for_chart:
    seg_data = df_agg[df_agg['segment'] == seg]
    seg_pivot = seg_data.pivot_table(index='year', columns='procedure_category',
                                     values='total_services', aggfunc='sum'
                                     ).reindex(columns=PROC_ORDER).fillna(0)
    market_data[seg] = seg_pivot.div(seg_pivot.sum(axis=1), axis=0) * 100

fig = plt.figure(figsize=(18, 14))
outer_gs = gridspec.GridSpec(2, 2, hspace=0.35, wspace=0.3,
                             left=0.06, right=0.94, top=0.90, bottom=0.06)
adv_procs  = ['Cardiac CTA', 'Cardiac MRI', 'Cardiac PET']
adv_colors = [COLOR_CTA, COLOR_MRI, COLOR_PET]

for idx, seg in enumerate(segments_for_chart):
    row, col = divmod(idx, 2)
    inner_gs = gridspec.GridSpecFromSubplotSpec(2, 1, subplot_spec=outer_gs[row, col],
                                                height_ratios=[3, 1.8], hspace=0.14)
    ax_main = fig.add_subplot(inner_gs[0])
    ax_inset = fig.add_subplot(inner_gs[1])

    seg_pct = market_data[seg]
    years = seg_pct.index.values

    y_stack = np.zeros(len(years))
    for i, proc in enumerate(PROC_ORDER):
        vals = seg_pct[proc].values if proc in seg_pct.columns else np.zeros(len(years))
        ax_main.fill_between(years, y_stack, y_stack + vals,
                             color=PROC_COLORS[i], label=proc, alpha=0.85)
        y_stack += vals

    ax_main.set_ylim(0, 100); ax_main.set_xlim(years.min(), years.max())
    ax_main.set_title(seg_titles[seg], fontsize=13, fontweight='bold', pad=8)
    ax_main.set_ylabel('Market Share (%)', fontsize=12)
    ax_main.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.0f}'))
    ax_main.set_xticks(years)
    ax_main.tick_params(labelsize=10)
    ax_main.grid(True, alpha=0.2)

    if idx == 0:
        h, l = ax_main.get_legend_handles_labels()
        ax_main.legend(h[::-1], l[::-1], fontsize=10, loc='center left',
                       framealpha=0.9, title='Modality (shaded band)', title_fontsize=10)

    y_stack_adv = np.zeros(len(years))
    for i, proc in enumerate(adv_procs):
        vals = seg_pct[proc].values if proc in seg_pct.columns else np.zeros(len(years))
        ax_inset.fill_between(years, y_stack_adv, y_stack_adv + vals,
                              color=adv_colors[i], label=proc, alpha=0.85)
        y_stack_adv += vals

    ax_inset.set_ylim(0, max(y_stack_adv.max() * 1.35, 0.5))
    ax_inset.set_xlim(years.min(), years.max())
    ax_inset.set_xlabel('Year', fontsize=12)
    ax_inset.set_ylabel('Advanced Share (%)', fontsize=11)
    ax_inset.set_xticks(years)
    ax_inset.tick_params(labelsize=10)
    ax_inset.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f'{x:.2f}'))
    ax_inset.grid(True, alpha=0.2)
    ax_inset.set_title('Zoom: Advanced Modalities (CTA + CMR + PET)', fontsize=10,
                       fontstyle='italic', color='#555555', pad=4)

    if idx == 0:
        h_a, l_a = ax_inset.get_legend_handles_labels()
        ax_inset.legend(h_a[::-1], l_a[::-1], fontsize=10, loc='upper left', framealpha=0.9)

    for yr_idx in [0, -1]:
        ax_inset.annotate(f'{y_stack_adv[yr_idx]:.2f}%',
                          (years[yr_idx], y_stack_adv[yr_idx]),
                          textcoords="offset points", xytext=(0, 8),
                          fontsize=10, ha='center', fontweight='bold', color='#5B005B')

fig.suptitle('Figure 2. Market Share: Composition of Cardiac Imaging Modalities\n'
             'Traditional (Echo + SPECT) vs Advanced (CTA + CMR + PET)',
             fontsize=15, fontweight='bold', y=0.97)
fig.text(0.06, 0.015,
         'Shaded bands = each modality’s share of total cardiac imaging volume. '
         'Bold labels on insets = advanced-modality share in first and last year.',
         fontsize=10, color='#555555')
save_pub_fig(fig, 'figure2_market_share', TIFF_PANEL_DPI)
plt.show()
plt.close()

national_trend = df_agg.groupby(['year', 'procedure_category'])['total_services'].sum().reset_index()
nat_pivot = national_trend.pivot_table(index='year', columns='procedure_category',
                                       values='total_services', aggfunc='sum'
                                       ).reindex(columns=PROC_ORDER).fillna(0)
nat_pct = nat_pivot.div(nat_pivot.sum(axis=1), axis=0) * 100
nat_pct['Traditional'] = nat_pct['Echo'] + nat_pct['SPECT']
nat_pct['Advanced'] = nat_pct['Cardiac CTA'] + nat_pct['Cardiac MRI'] + nat_pct['Cardiac PET']
print("National Market Share (%):")
print(nat_pct.round(3).to_string())
print("Figure 2 complete.\n")


# ══════════════════════════════════════════════════════════════════════════
#  FIGURES 3–7: State Choropleth Heatmaps (2018, 2023, and Delta)
# ══════════════════════════════════════════════════════════════════════════
print("Building Figures 3–7: State Choropleth Heatmaps...")

STATE_ABBR_MAP = {
    'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR',
    'California': 'CA', 'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE',
    'District of Columbia': 'DC', 'Florida': 'FL', 'Georgia': 'GA', 'Hawaii': 'HI',
    'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
    'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME',
    'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
    'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE',
    'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM',
    'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
    'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI',
    'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
    'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA',
    'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
}
TERR = ['AS', 'GU', 'MP', 'PR', 'VI']

cms_2023 = pd.read_excel(
    '/Users/sanjnapatel/Downloads/Data/original medicare enrollment 2023.xlsx',
    header=None, skiprows=4)
col_names_2023 = ['Area_of_Residence', 'State_Population', 'Total_Medicare_Enrollment',
                  'Total_Medicare_Pct', 'Original_Medicare_Enrollment',
                  'Original_Medicare_Pct', 'MA_Enrollment', 'MA_Pct',
                  'Metro_Enrollment', 'Micro_Enrollment', 'NonCore_Enrollment']
cms_2023.columns = col_names_2023[:len(cms_2023.columns)]
cms_2023 = cms_2023.dropna(subset=['Area_of_Residence', 'Original_Medicare_Enrollment'])
cms_2023 = cms_2023[~cms_2023['Area_of_Residence'].astype(str).str.contains(
    'BLANK|All Areas|United States|Notes|Source|¹|²|Area of Residence', na=False)]
cms_2023['STCD'] = cms_2023['Area_of_Residence'].astype(str).str.strip().map(STATE_ABBR_MAP)
cms_2023 = cms_2023.dropna(subset=['STCD'])
cms_2023 = cms_2023[~cms_2023['STCD'].isin(TERR)]
cms_2023['FFS'] = pd.to_numeric(cms_2023['Original_Medicare_Enrollment'], errors='coerce').astype(int)
state_ffs_2023 = dict(zip(cms_2023['STCD'], cms_2023['FFS']))
print(f"  2023 state enrollment loaded: {len(state_ffs_2023)} states, "
      f"national total = {sum(state_ffs_2023.values()):,}")

cms_2018 = pd.read_excel(
    '/Users/sanjnapatel/Downloads/Data/original medicare enrollment 2018.xlsx',
    header=None, skiprows=4)
col_names_2018 = ['Area_of_Residence', 'Total_Original_Medicare_Enrollees',
                  'Total_Aged', 'Aged_Without_ESRD']
if len(cms_2018.columns) > len(col_names_2018):
    for i in range(len(col_names_2018), len(cms_2018.columns)):
        col_names_2018.append(f'Extra_{i}')
cms_2018.columns = col_names_2018[:len(cms_2018.columns)]
cms_2018 = cms_2018.dropna(subset=['Area_of_Residence', 'Total_Original_Medicare_Enrollees'])
cms_2018 = cms_2018[~cms_2018['Area_of_Residence'].astype(str).str.contains(
    'BLANK|All Areas|United States|Notes|Source|¹|²|Area of Residence', na=False)]
cms_2018['STCD'] = cms_2018['Area_of_Residence'].astype(str).str.strip().map(STATE_ABBR_MAP)
cms_2018 = cms_2018.dropna(subset=['STCD'])
cms_2018 = cms_2018[~cms_2018['STCD'].isin(TERR)]
cms_2018['FFS'] = pd.to_numeric(cms_2018['Total_Original_Medicare_Enrollees'], errors='coerce').astype(int)
state_ffs_2018 = dict(zip(cms_2018['STCD'], cms_2018['FFS']))
print(f"  2018 state enrollment loaded: {len(state_ffs_2018)} states, "
      f"national total = {sum(state_ffs_2018.values()):,}")

def compute_state_rates(df_detail_sub, state_ffs_lookup):
    sp = (df_detail_sub.groupby(['state', 'procedure_category'])
          .agg(total_services=('Tot_Srvcs', 'sum')).reset_index())
    sp['ffs_enrollment'] = sp['state'].map(state_ffs_lookup)
    sp = sp.dropna(subset=['ffs_enrollment'])
    sp = sp[sp['ffs_enrollment'] > 0]
    sp['rate_per_1000'] = sp['total_services'] / sp['ffs_enrollment'] * 1000
    return sp

state_rates_2023 = compute_state_rates(df_detail[df_detail['year'] == 2023], state_ffs_2023)
state_rates_2018 = compute_state_rates(df_detail[df_detail['year'] == 2018], state_ffs_2018)

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'plotly', 'kaleido', '-q'])
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

delta_df = state_rates_2023[['state', 'procedure_category', 'rate_per_1000']].merge(
    state_rates_2018[['state', 'procedure_category', 'rate_per_1000']],
    on=['state', 'procedure_category'], suffixes=('_2023', '_2018'), how='outer'
).fillna(0)
delta_df['rate_delta'] = delta_df['rate_per_1000_2023'] - delta_df['rate_per_1000_2018']

CHORO_FONT = dict(size=14)   # plotly px sizes; 14 px ≈ 10.5 pt at export scale

for idx, proc in enumerate(PROC_ORDER):
    fig_num = idx + 3   # Figures 3–7

    p2018 = state_rates_2018[state_rates_2018['procedure_category'] == proc]
    p2023 = state_rates_2023[state_rates_2023['procedure_category'] == proc]
    p_delta = delta_df[delta_df['procedure_category'] == proc]
    if p2023.empty:
        print(f"  No data for {proc} — skipping")
        continue

    all_rates = pd.concat([p2018['rate_per_1000'], p2023['rate_per_1000']])
    rate_min, rate_max = all_rates.min(), all_rates.max()

    fig = make_subplots(
        rows=1, cols=3,
        specs=[[{'type': 'choropleth'}] * 3],
        subplot_titles=['2018', '2023', 'Change (2023 − 2018)'],
        horizontal_spacing=0.02,
    )
    fig.add_trace(go.Choropleth(
        locations=p2018['state'], z=p2018['rate_per_1000'],
        locationmode='USA-states', colorscale=PURPLE_SCALE,
        zmin=rate_min, zmax=rate_max,
        colorbar=dict(title='Rate/1K', len=0.6, x=0.29, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
    ), row=1, col=1)
    fig.add_trace(go.Choropleth(
        locations=p2023['state'], z=p2023['rate_per_1000'],
        locationmode='USA-states', colorscale=PURPLE_SCALE,
        zmin=rate_min, zmax=rate_max,
        colorbar=dict(title='Rate/1K', len=0.6, x=0.62, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
    ), row=1, col=2)
    delta_abs_max = max(abs(p_delta['rate_delta'].min()), abs(p_delta['rate_delta'].max()), 0.01)
    fig.add_trace(go.Choropleth(
        locations=p_delta['state'], z=p_delta['rate_delta'],
        locationmode='USA-states', colorscale=DELTA_SCALE,
        zmid=0, zmin=-delta_abs_max, zmax=delta_abs_max,
        colorbar=dict(title='Δ Rate/1K', len=0.6, x=0.96, thickness=14, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        hovertemplate='<b>%{location}</b><br>Δ Rate: %{z:+.2f}/1K<extra></extra>',
    ), row=1, col=3)

    fig.update_geos(scope='usa', projection_type='albers usa',
                    showlakes=True, lakecolor='rgb(200,220,240)', bgcolor='white')
    fig.update_annotations(font=dict(size=18))
    fig.update_layout(
        title=dict(
            text=(f'<b>Figure {fig_num}.</b> {proc} — Rate per 1,000 FFS Beneficiaries by State<br>'
                  f'<span style="font-size:13px">Purple scale: darker = higher rate. '
                  f'Diverging scale (right panel): red = rate decrease, blue = rate increase, '
                  f'white = no change. Territories excluded.</span>'),
            font=dict(size=18), x=0.5, xanchor='center',
        ),
        height=430, width=1500, paper_bgcolor='white',
        margin=dict(l=10, r=10, t=95, b=20),
    )

    filename = f'figure{fig_num}_{proc.lower().replace(" ", "_")}_state_maps.png'
    try:
        # width 1500 × scale 3 = 4500 px ≈ 300 DPI at a 15-inch print width
        fig.write_image(filename, width=1500, height=430, scale=3)
        print(f"  Figure {fig_num} saved: {filename}")
        png_to_tiff(filename, dpi=TIFF_RASTER_DPI)
    except Exception as e:
        print(f"  Could not save Figure {fig_num}: {e}")
    fig.show()

# Combined 2023 panel (unnumbered composite; optional Central Illustration)
fig_panel = make_subplots(
    rows=2, cols=3,
    specs=[[{'type': 'choropleth'}] * 3, [{'type': 'choropleth'}] * 2 + [None]],
    subplot_titles=[f'{p}' for p in PROC_ORDER],
    horizontal_spacing=0.02, vertical_spacing=0.08,
)
positions = [(1, 1), (1, 2), (1, 3), (2, 1), (2, 2)]
for i, (proc, (row, col)) in enumerate(zip(PROC_ORDER, positions)):
    pdata = state_rates_2023[state_rates_2023['procedure_category'] == proc]
    if pdata.empty:
        continue
    fig_panel.add_trace(go.Choropleth(
        locations=pdata['state'], z=pdata['rate_per_1000'],
        locationmode='USA-states', colorscale=PURPLE_SCALE,
        colorbar=dict(title='Rate/1K', len=0.35, thickness=12, tickfont=CHORO_FONT),
        marker_line_color='white', marker_line_width=0.5,
        showscale=(i == 0),
        hovertemplate='<b>%{location}</b><br>Rate: %{z:.2f}/1K<extra></extra>',
    ), row=row, col=col)
fig_panel.update_geos(scope='usa', projection_type='albers usa',
                      showlakes=True, lakecolor='rgb(200,220,240)', bgcolor='white')
fig_panel.update_annotations(font=dict(size=18))
fig_panel.update_layout(
    title=dict(text='<b>Cardiac Imaging Rates by State (2023) — All Modalities</b>'
                    '<br><span style="font-size:13px">Purple scale: darker = higher rate. '
                    'Scales differ by modality.</span>',
               font=dict(size=20), x=0.5, xanchor='center'),
    height=720, width=1400, paper_bgcolor='white',
    margin=dict(l=10, r=10, t=100, b=20),
)
try:
    fig_panel.write_image('figure_panel_all_modalities_2023.png', width=1400, height=720, scale=3)
    print("  Panel figure saved: figure_panel_all_modalities_2023.png")
    png_to_tiff('figure_panel_all_modalities_2023.png', dpi=TIFF_RASTER_DPI)
except Exception as e:
    print(f"  Panel save failed: {e}")
fig_panel.show()
print("Figures 3–7 complete.\n")


# ══════════════════════════════════════════════════════════════════════════
#  SUMMARY TABLE: State-level rates (2023)
# ══════════════════════════════════════════════════════════════════════════
print("=" * 80)
print("State-Level Procedure Rate per 1,000 FFS Beneficiaries (2023, Top 20)")
print("=" * 80)
summary_pivot = (state_rates_2023.pivot_table(
    index='state', columns='procedure_category',
    values='rate_per_1000', aggfunc='sum'
).reindex(columns=PROC_ORDER).fillna(0).round(2))
summary_pivot['All Cardiac'] = summary_pivot.sum(axis=1)
summary_pivot = summary_pivot.sort_values('All Cardiac', ascending=False)
print(summary_pivot.head(20).to_string())
print(f"\n({len(summary_pivot)} states total)")


# ══════════════════════════════════════════════════════════════════════════
#  MULTIVARIABLE NEGATIVE BINOMIAL — demographic adjustment (age + sex)
#     log(CTA count)_s = β0 + β1·density + β2·meanAge + β3·%female + log(FFS_s)
#     NB2. exp(β1) = density IRR. Covariates z-scored; density in natural units.
#  Figures: 8 (all-provider, MAIN TEXT), S1 (radiologist, supplement),
#           S2 (cardiologist, supplement), 9 (combined forest plot, MAIN
#           TEXT — final figure).
#  >>> EDIT GV_PUF_PATH to point at your downloaded GV PUF csv. <
# ══════════════════════════════════════════════════════════════════════════
GV_PUF_PATH = '/Users/sanjnapatel/Downloads/Medicare_GV_by_National_State_County_2024_copy*.csv'
GV_YEAR = 2023

try:
    import statsmodels.api as sm
    from statsmodels.discrete.discrete_model import NegativeBinomial
    from statsmodels.stats.outliers_influence import variance_inflation_factor
except ImportError:
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'statsmodels', '-q'])
    import statsmodels.api as sm
    from statsmodels.discrete.discrete_model import NegativeBinomial
    from statsmodels.stats.outliers_influence import variance_inflation_factor

import glob
Z95 = stats.norm.ppf(0.975)
BLUE, PURPLE, GRAY, CARD_RED = '#2166ac', '#8B3A8B', '#888780', '#C0392B'


def load_gv_demographics(path_glob, year):
    files = sorted(glob.glob(path_glob))
    if not files:
        raise FileNotFoundError(f"No GV PUF file matched: {path_glob}")
    gv = pd.concat([pd.read_csv(f, dtype=str, low_memory=False) for f in files],
                   ignore_index=True)
    gv.columns = [c.strip().upper() for c in gv.columns]
    print(f"  GV PUF file(s): {[f.split('/')[-1] for f in files]}")

    yr = pd.to_numeric(gv['YEAR'], errors='coerce')
    avail = sorted(yr.dropna().astype(int).unique())
    if year not in avail:
        raise ValueError(f"Year {year} not in GV PUF (available: {avail}).")

    lvl = gv['BENE_GEO_LVL'].astype(str).str.strip().str.lower()
    age = gv['BENE_AGE_LVL'].astype(str).str.strip().str.lower()
    gv = gv[(lvl == 'state') & (age.str.startswith('all')) & (yr == year)].copy()
    if gv.empty:
        raise ValueError("0 rows after State/all-ages/year filter.")

    name2abbr = {k.lower(): v for k, v in STATE_ABBR_MAP.items()}
    valid_abbr = set(STATE_ABBR_MAP.values())
    FIPS2ABBR = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT',
                 '10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL',
                 '18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD',
                 '25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE',
                 '32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND',
                 '39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD',
                 '47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
                 '55':'WI','56':'WY'}
    gv = gv.reset_index(drop=True)
    desc = gv['BENE_GEO_DESC'].fillna('').astype(str).str.strip()
    if 'BENE_GEO_CD' in gv.columns:
        cd = (gv['BENE_GEO_CD'].fillna('').astype(str).str.strip()
              .str.split('.').str[0].str.zfill(2))
    else:
        cd = pd.Series([''] * len(gv))

    def resolve(d, c):
        if d.upper() in valid_abbr:  return d.upper()
        if d.lower() in name2abbr:   return name2abbr[d.lower()]
        return FIPS2ABBR.get(c)

    gv['state'] = [resolve(d, c) for d, c in zip(desc, cd)]
    gv = gv.dropna(subset=['state']).reset_index(drop=True)   # drops territories + National

    def num(s):
        s = (s.astype(str).str.replace('%', '', regex=False)
                          .str.replace(',', '', regex=False).str.strip())
        return pd.to_numeric(s.replace({'*': np.nan, '.': np.nan, '': np.nan}),
                             errors='coerce')

    out = pd.DataFrame({'state': gv['state'].values})
    out['mean_age'] = num(gv['BENE_AVG_AGE']).values
    fem = num(gv['BENE_FEML_PCT']).values
    if np.nanmedian(fem) < 1.5:
        fem = fem * 100.0
    out['pct_female'] = fem
    out = out.dropna().drop_duplicates('state').reset_index(drop=True)
    if out.empty:
        raise ValueError("GV demographics empty after numeric coercion.")
    print(f"  GV PUF demographics usable: {len(out)} states (year {year})")
    return out


def fit_nb_design(X, counts, offset):
    pois = sm.GLM(counts, X, family=sm.families.Poisson(), offset=offset).fit()
    sp = np.append(pois.params, 1.0)
    res = None
    for method, kw in [('nm', dict(maxiter=8000)), ('lbfgs', dict(maxiter=3000))]:
        cand = NegativeBinomial(counts, X, offset=offset).fit(
                   start_params=sp, method=method, disp=0, **kw)
        if cand.mle_retvals.get('converged', False):
            res = cand; break
        res = res or cand
    return res, float(res.params[-1]), pois.pearson_chi2 / pois.df_resid


def irr_at(res, idx):
    b, se, p = res.params[idx], res.bse[idx], res.pvalues[idx]
    return np.exp(b), np.exp(b - Z95 * se), np.exp(b + Z95 * se), p


def density_partial_curve(res, x_grid, ncoef, per=1000):
    rows = np.zeros((len(x_grid), ncoef)); rows[:, 0] = 1.0; rows[:, 1] = x_grid
    beta = np.asarray(res.params)[:ncoef]
    cov = np.asarray(res.cov_params())[:ncoef, :ncoef]
    lp = rows @ beta
    se = np.sqrt(np.einsum('ij,jk,ik->i', rows, cov, rows))
    return np.exp(lp) * per, np.exp(lp - Z95 * se) * per, np.exp(lp + Z95 * se) * per


def vif_table(Xz_df):
    Xc = sm.add_constant(Xz_df.values)
    return {col: variance_inflation_factor(Xc, i + 1)
            for i, col in enumerate(Xz_df.columns)}


def run_test(df, density_col, density_label, title, color, fname,
             n_physicians, tiff_dpi=TIFF_LINEART_DPI):
    """NB2 unadjusted + adjusted; SINGLE-PANEL figure (scatter + both fits),
    with an inline text box reporting the unadjusted and adjusted density
    IRR, 95% CI, and p-value directly on the panel.

    n_physicians: nationally-deduplicated count of unique CTA-billing NPIs
    for this specialty group, passed in from COUNT(DISTINCT Rndrng_NPI)
    computed BEFORE any state-level grouping (avoids double-counting
    physicians who bill in more than one state)."""
    d = df.dropna(subset=['mean_age', 'pct_female']).copy()
    if len(d) < 10:
        raise ValueError(f"Only {len(d)} states merged demographics for '{density_label}'.")
    counts = d['total_services'].values.astype(float)
    offset = np.log(d['ffs_enrollment'].values.astype(float))
    dens = d[density_col].values.astype(float)

    for c in ['mean_age', 'pct_female']:
        d[c + '_z'] = (d[c] - d[c].mean()) / d[c].std(ddof=0)

    res_un, a_un, disp_un = fit_nb_design(sm.add_constant(dens), counts, offset)
    irr_un = irr_at(res_un, 1)

    Xz = d[[density_col, 'mean_age_z', 'pct_female_z']].copy()
    res_adj, a_adj, _ = fit_nb_design(sm.add_constant(Xz.values), counts, offset)
    irr_adj = irr_at(res_adj, 1)
    ncoef_adj = Xz.shape[1] + 1
    vifs = vif_table(Xz.rename(columns={density_col: 'density'}))

    n_states = len(d)

    # ---- console report ----
    print("=" * 76)
    print(f"{title}   (n = {n_states} states, {n_physicians:,} unique physicians, 2023)")
    print("Outcome = raw CTA counts | offset = log(FFS) | NB2 | covariates z-scored")
    print("-" * 76)
    names = ['intercept', density_label, 'mean age (+1 SD)', '% female (+1 SD)']
    print(f"{'Adjusted-model term':<24}{'IRR':>9}{'95% CI':>20}{'p':>10}")
    for i, nm in enumerate(names):
        irr, lo, hi, p = irr_at(res_adj, i)
        pstr = "<0.001" if p < 0.001 else f"{p:.3f}"
        if i == 0:
            print(f"{nm:<24}{'—':>9}{'(baseline)':>20}{'':>10}")
        else:
            print(f"{nm:<24}{irr:>9.4f}{f'{lo:.4f}-{hi:.4f}':>20}{pstr:>10}")
    print("-" * 76)
    print(f"DENSITY IRR — unadjusted: {irr_un[0]:.4f} ({irr_un[1]:.4f}-{irr_un[2]:.4f})")
    print(f"DENSITY IRR — adjusted  : {irr_adj[0]:.4f} ({irr_adj[1]:.4f}-{irr_adj[2]:.4f})")
    print(f"VIF: " + ", ".join(f"{k}={v:.2f}" for k, v in vifs.items()) + "   (>5 = concern)")
    print(f"NB alpha: unadj {a_un:.3f} / adj {a_adj:.3f} | Poisson dispersion ~{disp_un:.0f}")
    print("=" * 76)

    # ---- SINGLE-PANEL figure ----
    fig, ax = plt.subplots(figsize=(10.5, 7.0))
    fig.patch.set_facecolor('white')

    y = d['rate_per_1000'].values
    ax.scatter(dens, y, color=color, s=70, alpha=0.85,
               edgecolors='white', linewidths=0.7, zorder=3,
               label='State (labeled with postal code)')
    xg = np.linspace(dens.min(), dens.max(), 300)
    ru, _, _ = density_partial_curve(res_un, xg, 2)
    ra, la, ha = density_partial_curve(res_adj, xg, ncoef_adj)
    ax.fill_between(xg, la, ha, color=color, alpha=0.10, zorder=2,
                    label='95% CI of adjusted fit (shaded band)')
    ax.plot(xg, ru, color=GRAY, lw=2.2, ls=':', zorder=4,
            label='Unadjusted NB fit (dotted line)')
    ax.plot(xg, ra, color=color, lw=2.4, ls='--', zorder=5,
            label='Adjusted NB fit, age & %female at mean (dashed line)')
    for _, r in d.iterrows():
        ax.annotate(r['state'], (r[density_col], r['rate_per_1000']),
                    fontsize=10, color='#333333', fontfamily='monospace',
                    xytext=(4, 3), textcoords='offset points')
    ax.set_xlabel(density_label, fontsize=12, fontweight='bold')
    ax.set_ylabel('CTA Rate per 1,000 FFS Beneficiaries', fontsize=12, fontweight='bold')

    # ---- Inline IRR / CI / p-value text box (unadjusted + adjusted) --------
    un_irr, un_lo, un_hi, un_p = irr_un
    adj_irr, adj_lo, adj_hi, adj_p = irr_adj
    un_pstr  = 'p<0.001' if un_p  < 0.001 else f'p={un_p:.3f}'
    adj_pstr = 'p<0.001' if adj_p < 0.001 else f'p={adj_p:.3f}'
    stats_text = (
        f"Unadjusted IRR = {un_irr:.3f} ({un_lo:.3f}–{un_hi:.3f}), {un_pstr}\n"
        f"Adjusted IRR   = {adj_irr:.3f} ({adj_lo:.3f}–{adj_hi:.3f}), {adj_pstr}\n"
        f"n = {n_states} states, {n_physicians:,} physicians"
    )
    ax.text(0.97, 0.05, stats_text, transform=ax.transAxes,
            fontsize=10, ha='right', va='bottom', fontfamily='monospace',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='white',
                      edgecolor='#cccccc', alpha=0.95))

    ax.legend(fontsize=10, framealpha=0.9, loc='upper left')
    ax.tick_params(labelsize=10)
    ax.grid(True, alpha=0.2, linewidth=0.5)
    ax.set_title(title, fontsize=13, fontweight='bold', pad=12)

    plt.tight_layout()
    save_pub_fig(fig, fname, tiff_dpi)
    plt.show(); plt.close()
    return dict(irr_un=irr_un, irr_adj=irr_adj, n=n_states, n_physicians=n_physicians)


# === DATA & MODELS (2023, state-level; full territory exclusion) ============
print("Building multivariable NB (age + sex adjustment), 2023...")
demo = load_gv_demographics(GV_PUF_PATH, GV_YEAR)
state_ffs = state_ffs_2023

_all = con.execute(f"""
    SELECT Rndrng_NPI, Rndrng_Prvdr_State_Abrvtn AS state, SUM(Tot_Srvcs) AS total_services
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL} GROUP BY Rndrng_NPI, state
""").fetchdf()
_vol = (_all.groupby('state').agg(total_services=('total_services', 'sum'),
        total_unique_npis=('Rndrng_NPI', 'nunique')).reset_index())

# Radiologist NPIs
_rad = con.execute(f"""
    SELECT Rndrng_NPI, Rndrng_Prvdr_State_Abrvtn AS state
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL} AND Rndrng_Prvdr_Type IN {RAD_TYPES}
    GROUP BY Rndrng_NPI, state
""").fetchdf()
_radn = _rad.groupby('state').agg(rad_unique_npis=('Rndrng_NPI', 'nunique')).reset_index()
df_rad = _vol.merge(_radn, on='state', how='left')
df_rad['rad_unique_npis'] = df_rad['rad_unique_npis'].fillna(0).astype(int)
df_rad['ffs_enrollment'] = df_rad['state'].map(state_ffs)
df_rad = df_rad.dropna(subset=['ffs_enrollment'])
df_rad['rate_per_1000']     = df_rad['total_services']  / df_rad['ffs_enrollment'] * 1_000
df_rad['rad_npis_per_100k'] = df_rad['rad_unique_npis'] / df_rad['ffs_enrollment'] * 100_000
df_rad = df_rad[df_rad['rad_unique_npis'] > 0].merge(demo, on='state', how='left')

# All-provider NPIs
df_all = (_all.groupby('state').agg(total_services=('total_services', 'sum'),
          unique_npis=('Rndrng_NPI', 'nunique')).reset_index())
df_all['ffs_enrollment'] = df_all['state'].map(state_ffs)
df_all = df_all.dropna(subset=['ffs_enrollment'])
df_all['rate_per_1000'] = df_all['total_services'] / df_all['ffs_enrollment'] * 1_000
df_all['npis_per_100k'] = df_all['unique_npis']    / df_all['ffs_enrollment'] * 100_000
df_all = df_all.merge(demo, on='state', how='left')

# Cardiologist NPIs
_card = con.execute(f"""
    SELECT Rndrng_NPI, Rndrng_Prvdr_State_Abrvtn AS state
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL} AND Rndrng_Prvdr_Type IN {CARD_TYPES}
    GROUP BY Rndrng_NPI, state
""").fetchdf()
_cardn = _card.groupby('state').agg(card_unique_npis=('Rndrng_NPI', 'nunique')).reset_index()
df_card = _vol.merge(_cardn, on='state', how='left')
df_card['card_unique_npis'] = df_card['card_unique_npis'].fillna(0).astype(int)
df_card['ffs_enrollment'] = df_card['state'].map(state_ffs)
df_card = df_card.dropna(subset=['ffs_enrollment'])
df_card['rate_per_1000']      = df_card['total_services']   / df_card['ffs_enrollment'] * 1_000
df_card['card_npis_per_100k'] = df_card['card_unique_npis'] / df_card['ffs_enrollment'] * 100_000
df_card = df_card[df_card['card_unique_npis'] > 0].merge(demo, on='state', how='left')


# ══════════════════════════════════════════════════════════════════════════
#  NATIONALLY-DEDUPLICATED PHYSICIAN COUNTS (2023 CTA billers, by specialty)
#  COUNT(DISTINCT NPI) across ALL states combined — a physician billing in
#  more than one state is counted ONCE here (unlike summing per-state
#  unique_npis, which would double-count multi-state billers).
# ══════════════════════════════════════════════════════════════════════════
n_physicians_all = con.execute(f"""
    SELECT COUNT(DISTINCT Rndrng_NPI)
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL}
""").fetchone()[0]

n_physicians_rad = con.execute(f"""
    SELECT COUNT(DISTINCT Rndrng_NPI)
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL} AND Rndrng_Prvdr_Type IN {RAD_TYPES}
""").fetchone()[0]

n_physicians_card = con.execute(f"""
    SELECT COUNT(DISTINCT Rndrng_NPI)
    FROM medicare WHERE year=2023 AND HCPCS_Cd='75574' AND Rndrng_Prvdr_Cntry='US'
      {EXCL_SQL} AND Rndrng_Prvdr_Type IN {CARD_TYPES}
""").fetchone()[0]

print(f"National unique CTA-billing NPIs, 2023: "
      f"All={n_physicians_all:,} | Radiologists={n_physicians_rad:,} | "
      f"Cardiologists={n_physicians_card:,}")

# ── Which states had ZERO billers of each specialty? ────────────────────────
all_50_dc = set(state_ffs_2023.keys()) - set(TERR)   # 50 states + DC

states_with_rad  = set(df_rad['state'])
states_with_card = set(df_card['state'])
states_with_any  = set(df_all['state'])

missing_any_biller  = sorted(all_50_dc - states_with_any)
missing_rad_biller  = sorted(all_50_dc - states_with_rad)
missing_card_biller = sorted(all_50_dc - states_with_card)

print("\n" + "=" * 76)
print("STATES WITH ZERO CTA-BILLING PHYSICIANS BY SPECIALTY (2023)")
print("=" * 76)
print(f"No CTA billers of ANY specialty ({len(missing_any_biller)}): "
      f"{missing_any_biller if missing_any_biller else 'none'}")
print(f"No radiologist CTA billers      ({len(missing_rad_biller)}): "
      f"{missing_rad_biller if missing_rad_biller else 'none'}")
print(f"No cardiologist CTA billers     ({len(missing_card_biller)}): "
      f"{missing_card_biller if missing_card_biller else 'none'}")
print("=" * 76 + "\n")


# ── FIGURE 8 (main text): All-provider density NB curve ─────────────────────
r_all = run_test(df_all, 'npis_per_100k', 'CTA-Billing NPIs per 100,000 FFS Beneficiaries',
    'Figure 8. All-Provider Density vs CTA Rate — Multivariable NB (age + %female), 2023',
    PURPLE, 'figure8_nb_all_density', n_physicians=n_physicians_all)

# ── SUPPLEMENTAL FIGURE S1: Radiologist density NB curve ────────────────────
r_rad = run_test(df_rad, 'rad_npis_per_100k', 'Radiologist NPIs per 100,000 FFS Beneficiaries',
    'Supplemental Figure S1. Radiologist Density vs CTA Rate — Multivariable NB, 2023',
    BLUE, 'figureS1_nb_rad_density', n_physicians=n_physicians_rad)

# ── SUPPLEMENTAL FIGURE S2: Cardiologist density NB curve ───────────────────
r_card = run_test(df_card, 'card_npis_per_100k', 'Cardiologist NPIs per 100,000 FFS Beneficiaries',
    'Supplemental Figure S2. Cardiologist Density vs CTA Rate — Multivariable NB, 2023',
    CARD_RED, 'figureS2_nb_card_density', n_physicians=n_physicians_card)


# ══════════════════════════════════════════════════════════════════════════
#  TABLE 1 — Provider specialty distribution by modality (2023)
#  Single source of truth for the forest-plot share annotations.
# ══════════════════════════════════════════════════════════════════════════
t1 = con.execute(f"""
    SELECT {MODALITY_CASE} AS modality,
        CASE
            WHEN Rndrng_Prvdr_Type IN {RAD_TYPES}  THEN 'Radiology'
            WHEN Rndrng_Prvdr_Type IN {CARD_TYPES} THEN 'Cardiology'
            ELSE 'Other'
        END AS spec_group,
        SUM(Tot_Srvcs) AS total_services
    FROM medicare
    WHERE year = 2023 AND Rndrng_Prvdr_Cntry = 'US'
      {EXCL_SQL}
      AND ({MODALITY_CASE}) IS NOT NULL
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
print("TABLE 1 — Provider specialty distribution by modality, 2023 (final)")
print("=" * 78)
print(table1.round(1).to_string(
    formatters={'Total Volume': lambda v: f"{int(v):,}"}))

# Shares for the forest plot come DIRECTLY from Table 1's CTA row.
cta_row = table1.loc['Cardiac CTA']
SHARE_RAD  = cta_row['Radiology %']    # expected 59.1
SHARE_CARD = cta_row['Cardiology %']   # expected 37.2
print(f"\nForest-plot annotations from Table 1: "
      f"Radiology {SHARE_RAD:.1f}% | Cardiology {SHARE_CARD:.1f}%")


# ══════════════════════════════════════════════════════════════════════════
#  FIGURE 9 (main text, FINAL FIGURE): Combined Forest Plot  — v4
#  - numeric column right-aligned into a fixed results gutter (IRR + p only)
#  - CI dropped from inline labels (shown by the bars; full CI in console table)
#  - caption wrapped into one centered, boxed frame
#  - y-axis labels report NATIONAL unique physician n ONLY (states dropped)
# ══════════════════════════════════════════════════════════════════════════
print("\nBuilding Figure 9: Combined density-IRR forest plot...")

import textwrap

FOREST_ROWS = [
    ('All CTA-billing providers', 'all interpretations',                   r_all,  PURPLE),
    ('Radiologists',              f'{SHARE_RAD:.1f}% of interpretations',   r_rad,  BLUE),
    ('Cardiologists',             f'{SHARE_CARD:.1f}% of interpretations',  r_card, CARD_RED),
]

fig, ax = plt.subplots(figsize=(11.5, 5.8))
fig.patch.set_facecolor('white')
Y_OFFSET = {'un': +0.17, 'adj': -0.17}

# Fixed results gutter: whiskers live in 0.95–1.35, numbers align at RESULT_X.
RESULT_X = 1.40
SEP_X    = 1.375

for i, (label, share_note, r, color) in enumerate(FOREST_ROWS):
    for key, (irr, lo, hi, p) in [('un', r['irr_un']), ('adj', r['irr_adj'])]:
        yy = i + Y_OFFSET[key]
        c = GRAY if key == 'un' else color
        marker = 'o' if key == 'un' else 's'
        ax.plot([lo, hi], [yy, yy], color=c, lw=2.4, zorder=2, solid_capstyle='round')
        ax.scatter([irr], [yy], color=c, s=95, marker=marker, zorder=3,
                   edgecolors='white', linewidths=1)
        # right-aligned numeric column (IRR + p only), monospace keeps it tidy
        pstr = 'p<0.001' if p < 0.001 else f'p={p:.3f}'
        ax.text(RESULT_X, yy, f"{irr:.3f}    {pstr}", va='center', ha='left',
                fontsize=10, fontfamily='monospace', color='#333333')

# column header for the gutter
ax.text(RESULT_X, -0.62, 'IRR      p-value', va='center', ha='left',
        fontsize=9.5, fontfamily='monospace', fontweight='bold', color='#555555')

# null reference + faint separator before the results gutter
ax.axvline(1.0,   color='#777777', lw=1.2, ls='--', zorder=1)
ax.axvline(SEP_X, color='#dddddd', lw=1.0, zorder=1)

ax.set_yticks(range(len(FOREST_ROWS)))
# NOTE: n now reports physicians only — state count dropped per request.
ax.set_yticklabels(
    [f"{label}\n({note}, n={r['n_physicians']:,})"
     for label, note, r, _ in FOREST_ROWS],
    fontsize=11
)
ax.invert_yaxis()
ax.set_ylim(len(FOREST_ROWS) - 0.5, -0.75)

ax.set_xscale('log')
xticks = [0.95, 1.0, 1.05, 1.1, 1.15, 1.2, 1.25, 1.3, 1.35]
ax.set_xticks(xticks)
ax.set_xticklabels([f'{t:g}' for t in xticks], fontsize=10)
ax.xaxis.set_minor_locator(mticker.NullLocator())
ax.set_xlim(0.95, 1.62)          # room for the results gutter; ticks stop at 1.35
ax.set_xlabel('Density Incidence Rate Ratio (per +1 NPI per 100,000 FFS beneficiaries)',
              fontsize=12, fontweight='bold')

# compact legend (short labels so it clears the top whisker at ~1.15)
legend_elems = [
    Line2D([0], [0], marker='o', color=GRAY, lw=2.4, markersize=9,
           markeredgecolor='white', label='Unadjusted'),
    Line2D([0], [0], marker='s', color='#444444', lw=2.4, markersize=9,
           markeredgecolor='white', label='Adjusted (age, sex)'),
    Line2D([0], [0], color='#777777', lw=1.2, ls='--', label='Null (IRR = 1.0)'),
]
ax.legend(handles=legend_elems, loc='upper left', fontsize=9.5,
          framealpha=0.95, borderaxespad=0.8, handlelength=1.6)

ax.grid(True, axis='x', alpha=0.2, linewidth=0.5)
ax.spines[['top', 'right']].set_visible(False)

ax.set_title(
    'Figure 9. CTA Utilization vs Imaging Physician Density (2023):\n'
    'Density IRRs Before and After Demographic Adjustment, by Interpreting Specialty',
    fontsize=13, fontweight='bold', pad=12,
)

# ── caption: wrapped into a single centered, boxed frame ────────────────────
caption = (
    'Horizontal bars = 95% CIs. NB2 models, state-level. n = nationally deduplicated '
    'unique CTA-billing NPIs (COUNT DISTINCT across all states) for each specialty group. '
    'Models fit on states with ≥1 qualifying NPI and complete demographic data; states with '
    'no billers of a given specialty are excluded from that model. Offset = log(FFS enrollment). '
    'Adjusted models include z-scored mean age and % female. Interpretation shares from Table 1. '
    'IRR > 1 indicates higher CTA rates in higher-density states. CIs overlap across specialties; '
    'between-specialty differences were not formally tested.'
)
fig.text(0.5, -0.06, textwrap.fill(caption, width=112),
         ha='center', va='top', fontsize=9, color='#555555', linespacing=1.4,
         bbox=dict(boxstyle='round,pad=0.7', facecolor='#f7f7f7',
                   edgecolor='#cccccc', linewidth=0.8))

plt.tight_layout()
save_pub_fig(fig, 'figure9_density_irr_forest', TIFF_LINEART_DPI)
plt.show()
plt.close()

# ══════════════════════════════════════════════════════════════════════════
#  FINAL FIGURE MANIFEST
# ══════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 80)
print("ALL FIGURES COMPLETE — FINAL NUMBERING")
print("=" * 80)
print("""
MAIN TEXT
  Figure 1:  Volume / enrollment / rate decomposition (5 modalities × 3 metrics)
  Figure 2:  Market share — stacked area with advanced-modality zoom insets
  Figure 3:  Echo        — state rates, 2018 / 2023 / change
  Figure 4:  SPECT       — state rates, 2018 / 2023 / change
  Figure 5:  Cardiac CTA — state rates, 2018 / 2023 / change
  Figure 6:  Cardiac MRI — state rates, 2018 / 2023 / change
  Figure 7:  Cardiac PET — state rates, 2018 / 2023 / change
  Figure 8:  All-provider density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure 9:  Combined forest plot — density IRRs before/after adjustment (FINAL)
  (unnumbered composite: all-modality 2023 state panel)

SUPPLEMENT
  Figure S1: Radiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)
  Figure S2: Cardiologist density vs CTA rate — multivariable NB
             (single panel + inline unadjusted/adjusted IRR, CI, p)

OUTPUT FORMATS
  Every matplotlib figure: .png (300 DPI working copy) + .tiff (LZW-compressed;
  line art at {la} DPI, large multi-panels at {mp} DPI — raise to 1200 for
  final submission if file sizes allow).
  Plotly choropleths: .png (~300 DPI at print width) + converted .tiff (300 DPI).

POPULATION
  50 states + DC. Excluded everywhere: AS, GU, MP, PR, VI, and unknown/invalid
  state codes (XX, ZZ, blank).

Enrollment: CMS Program Statistics — Original Medicare Enrollment
State enrollment: CMS Monthly Enrollment Reports (2018, 2023)
Claims: Medicare Physician & Other Practitioners by Provider and Service
""".format(la=TIFF_LINEART_DPI, mp=TIFF_PANEL_DPI))
