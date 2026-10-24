"""Single source of truth: paths, table names, population rules, HCPCS codes, enrollment, DPI."""
import os
from pathlib import Path

# ==========================================================================
# PATHS & DATABASE — override with environment variables (see .env.example)
# ==========================================================================
REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path=None):
    """Read KEY=VALUE lines from the repo's .env into os.environ (never overriding variables already set).

    Each laptop keeps its own .env (gitignored) — scripts/setup_laptop.sh writes the data paths it finds there.
    """
    path = Path(path or REPO_ROOT / '.env')
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.split(' #', 1)[0].strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = (x.strip() for x in line.split('=', 1))
        if value and key not in os.environ:
            os.environ[key] = value.strip('"').strip("'")


load_dotenv()


def _path(env_var, default):
    """Env-var path, resolved against the repo root when relative."""
    p = Path(os.environ.get(env_var) or default).expanduser()
    return p if p.is_absolute() else REPO_ROOT / p


OUTPUT_DIR = _path('CARDIAC_OUTPUT_DIR', 'outputs')   # only for runs made with record=False
LOG_DIR = _path('CARDIAC_LOG_DIR', 'logs')
# One folder per run (figures, tables, console.log, manifest.json, gallery.html, all_figures.pdf).
# Kept outside the iCloud-synced Desktop by default; the repo gets a `runs` link to it.
RUNS_DIR = _path('CARDIAC_RUNS_DIR', Path.home() / 'Downloads' / 'cms_runs')
SAVE_TIFF = os.environ.get('CARDIAC_SAVE_TIFF', '1') != '0'   # submission TIFFs (slow, large)
# Upload each finished run as a GitHub Release on its code-snapshot tag (needs the `gh` CLI, logged in).
PUBLISH_RUNS = os.environ.get('CARDIAC_PUBLISH_RUNS', '1') != '0'
# The results app syncs runs with GitHub (both ways) in the background when it starts.
SYNC_ON_START = os.environ.get('CARDIAC_SYNC_ON_START', '1') != '0'

# Chart discussions (local app): saved on this Mac only; consolidated hypotheses go to docs/hypotheses/.
CONVERSATIONS_DIR = _path('CARDIAC_CONVERSATIONS_DIR', Path.home() / 'Downloads' / 'cms_conversations')
CHAT_BACKEND = os.environ.get('CARDIAC_CHAT_BACKEND', 'auto')   # auto | claude-code | api | handoff
CLAUDE_BIN = os.environ.get('CARDIAC_CLAUDE_BIN', 'claude')      # Claude Code CLI used by the claude-code backend
CHAT_MODEL = os.environ.get('CARDIAC_CHAT_MODEL', 'claude-opus-5-5')
APP_PORT = int(os.environ.get('CARDIAC_APP_PORT', '8765'))

# Raw inputs (read only by scripts/convert_cms_to_parquet.py and scripts/build_database.py)
PARQUET_DIR   = _path('CMS_PARQUET_DIR', Path.home() / 'Downloads' / 'cms_parquet')
REFERENCE_DIR = _path('CMS_REFERENCE_DIR', Path.home() / 'Downloads' / 'Data')   # enrollment .xlsx
GV_PUF_GLOB   = os.path.expanduser(os.environ.get('CMS_GV_GLOB') or str(
    Path.home() / 'Downloads' / 'Medicare_GV_by_National_State_County_2024_copy*.csv'))

# Analysis database: local DuckDB file built from the Parquet files.
# Set CARDIAC_DB=md:<name> (plus MOTHERDUCK_TOKEN) to use a MotherDuck copy instead.
DATABASE = os.path.expanduser(os.environ.get('CARDIAC_DB') or str(PARQUET_DIR / 'cms.duckdb'))

CLAIMS_TABLE     = 'partb_provider_service'  # Physician & Other Practitioners PUF, all years + `year`
ENROLLMENT_TABLE = 'state_ffs_enrollment'    # cleaned (year, state, ffs)
GV_TABLE         = 'gv_puf'                  # Geographic Variation PUF, raw (all VARCHAR)

# ==========================================================================
# STUDY WINDOW
# ==========================================================================
BASE_YEAR = 2018
END_YEAR  = 2023
GV_YEAR   = 2023
CTA_CODE  = '75574'

# TIFF export settings (JACC: color/grayscale >=300 DPI, line art >=1200 DPI)
TIFF_LINEART_DPI = 1200   # single-panel matplotlib line art
TIFF_PANEL_DPI   = 600    # large multi-panel line art (1200 makes >20k-px files;
                          # raise to 1200 for final submission if files are manageable)
TIFF_RASTER_DPI  = 300    # plotly choropleths (raster)

# ==========================================================================
# ANALYTIC POPULATION & SPECIALTY DEFINITIONS
# 50 states + DC only. Excluded everywhere: American Samoa, Guam, Northern
# Mariana Islands, Puerto Rico, US Virgin Islands, and unknown/invalid codes.
# ==========================================================================
EXCLUDED_AREAS = ('AS', 'GU', 'MP', 'PR', 'VI', 'XX', 'ZZ', '')
EXCL_SQL = f"AND Rndrng_Prvdr_State_Abrvtn NOT IN {EXCLUDED_AREAS}"
TERR = ['AS', 'GU', 'MP', 'PR', 'VI']

RAD_TYPES  = ('Diagnostic Radiology', 'Nuclear Medicine', 'Interventional Radiology')
CARD_TYPES = ('Cardiology', 'Interventional Cardiology',
              'Clinical Cardiac Electrophysiology',
              'Advanced Heart Failure and Transplant Cardiology')

# Cardiac PET = myocardial perfusion PET: 78491/78492 (PET only) + 78430/78431 (PET with concurrent CT, CPT 2020+).
# Not counted: 78432/78433 (perfusion + metabolic), 78429/78459 (metabolic/viability), 78434 (blood-flow add-on to
# a perfusion study, never a separate study). Set by the user 2026-10-24 (docs/PENDING.md item 1).
MODALITY_CASE = """
    CASE
        WHEN HCPCS_Cd BETWEEN '75557' AND '75565' THEN 'Cardiac MRI'
        WHEN HCPCS_Cd = '75574'                    THEN 'Cardiac CTA'
        WHEN HCPCS_Cd IN ('78491','78492','78430','78431') THEN 'Cardiac PET'
        WHEN HCPCS_Cd IN ('93306','93307','93308')  THEN 'Echo'
        WHEN HCPCS_Cd IN ('78451','78452')          THEN 'SPECT'
    END
"""

MODALITY_TYPE_CASE = """
    CASE
        WHEN HCPCS_Cd BETWEEN '75557' AND '75565' THEN 'Advanced'
        WHEN HCPCS_Cd = '75574'                    THEN 'Advanced'
        WHEN HCPCS_Cd IN ('78491','78492','78430','78431') THEN 'Advanced'
        WHEN HCPCS_Cd IN ('93306','93307','93308')  THEN 'Traditional'
        WHEN HCPCS_Cd IN ('78451','78452')          THEN 'Traditional'
    END
"""

CARDIAC_HCPCS_WHERE = """
    (HCPCS_Cd BETWEEN '75557' AND '75565'
     OR HCPCS_Cd = '75574'
     OR HCPCS_Cd IN ('78491','78492','78430','78431')
     OR HCPCS_Cd IN ('93306','93307','93308')
     OR HCPCS_Cd IN ('78451','78452'))
"""

# COMPARATOR PROCEDURES — not imaging modalities: each gets a Figure 1 column and its own state map, and is kept out
# of the modality definitions above so market share, Table 1 and the Traditional/Advanced totals stay imaging-only.
# Invasive coronary angiography (diagnostic catheterization with coronary angiography). Added by the user 2026-10-24.
ICA_LABEL = 'Invasive Coronary Angiography'
ICA_CODES = ('93454', '93455', '93456', '93457', '93458', '93459', '93460', '93461')
# Transcatheter aortic valve replacement, all access routes (33367–33369 bypass add-ons excluded). Added by the user
# 2026-10-24. Usually billed by two co-surgeons (cardiology + cardiac surgery), so services ≈ 2 × procedures.
TAVR_LABEL = 'TAVR'
TAVR_CODES = ('33361', '33362', '33363', '33364', '33365', '33366')
COMPARATORS = {ICA_LABEL: ICA_CODES, TAVR_LABEL: TAVR_CODES}   # Figure 1 column order = this order

# ==========================================================================
# ENROLLMENT: CMS Program Statistics — Original Medicare Enrollment
# ==========================================================================
MEDICARE_ENROLLMENT = {
    2018: 37_994_241, 2019: 37_898_471, 2020: 37_094_414,
    2021: 35_681_342, 2022: 34_596_702, 2023: 33_694_472,
}

# ==========================================================================
# GEOGRAPHY LOOKUPS
# ==========================================================================
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

FIPS2ABBR = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT',
             '10':'DE','11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL',
             '18':'IN','19':'IA','20':'KS','21':'KY','22':'LA','23':'ME','24':'MD',
             '25':'MA','26':'MI','27':'MN','28':'MS','29':'MO','30':'MT','31':'NE',
             '32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND',
             '39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD',
             '47':'TN','48':'TX','49':'UT','50':'VT','51':'VA','53':'WA','54':'WV',
             '55':'WI','56':'WY'}
