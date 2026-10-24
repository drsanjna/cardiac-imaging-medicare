"""Publication typography (JACC: optimal 12 pt, min 10 pt) and the shared color palette."""
import matplotlib.pyplot as plt

from . import config


def apply_rcparams():
    """Set matplotlib defaults used by every figure."""
    plt.rcParams['figure.dpi'] = 150
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.size'] = 12          # base lettering 12 pt
    plt.rcParams['axes.titlesize'] = 13
    plt.rcParams['axes.labelsize'] = 12
    plt.rcParams['xtick.labelsize'] = 10    # never below 10 pt
    plt.rcParams['ytick.labelsize'] = 10
    plt.rcParams['legend.fontsize'] = 10


COLOR_ECHO  = '#7B8FA1'
COLOR_SPECT = '#A8BED1'
COLOR_CTA   = '#8B3A8B'
COLOR_MRI   = '#C154C1'
COLOR_PET   = '#E88BE8'

PROC_ORDER  = ['Echo', 'SPECT', 'Cardiac CTA', 'Cardiac MRI', 'Cardiac PET']
PROC_COLORS = [COLOR_ECHO, COLOR_SPECT, COLOR_CTA, COLOR_MRI, COLOR_PET]
# Figure 1 adds the comparator procedures (config.COMPARATORS: ICA, TAVR) after the imaging modalities.
FIG1_ORDER  = PROC_ORDER + list(config.COMPARATORS)

COLOR_VOLUME     = '#C0392B'
COLOR_ENROLLMENT = '#7F8C8D'
COLOR_RATE       = '#2471A3'

# Density-model figures (8, 9, S1, S2)
BLUE, PURPLE, GRAY, CARD_RED = '#2166ac', '#8B3A8B', '#888780', '#C0392B'

PURPLE_SCALE = [
    [0.0,  '#f2e6f7'], [0.15, '#e0c7ee'], [0.3,  '#cc9edf'],
    [0.45, '#b676d0'], [0.6,  '#9b4dba'], [0.75, '#7e2ea0'],
    [0.9,  '#5e1580'], [1.0,  '#3b0062'],
]
DELTA_SCALE = [
    [0.0,  '#b2182b'], [0.25, '#ef8a62'], [0.5,  '#f7f7f7'],
    [0.75, '#67a9cf'], [1.0,  '#2166ac'],
]

CHORO_FONT = dict(size=14)   # plotly px sizes; 14 px ≈ 10.5 pt at export scale
