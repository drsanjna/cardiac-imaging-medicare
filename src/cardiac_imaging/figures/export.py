"""Save figures to OUTPUT_DIR as PNG (300 DPI) + LZW TIFF in tiff/, and display them only inside notebooks."""
from pathlib import Path

import matplotlib.pyplot as plt

from .. import config


def in_notebook():
    """True when running inside a Jupyter kernel (figures are then shown inline)."""
    try:
        from IPython import get_ipython
        return get_ipython() is not None and 'IPKernelApp' in get_ipython().config
    except Exception:
        return False


def out_path(name):
    """Path for an output file in OUTPUT_DIR (created if needed)."""
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return config.OUTPUT_DIR / name


def tiff_path(stem):
    """Path for a submission TIFF in OUTPUT_DIR/tiff (created if needed)."""
    d = config.OUTPUT_DIR / 'tiff'
    d.mkdir(parents=True, exist_ok=True)
    return d / f'{stem}.tiff'


def save_pub_fig(fig, stem, tiff_dpi):
    """Save a matplotlib figure as working PNG (300 DPI) + submission TIFF (LZW), then show/close it."""
    fig.savefig(out_path(f'{stem}.png'), bbox_inches='tight', dpi=300)
    if not config.SAVE_TIFF:
        print(f"  Saved: {stem}.png (300 DPI); TIFF skipped (CARDIAC_SAVE_TIFF=0)")
    else:
        try:
            fig.savefig(tiff_path(stem), bbox_inches='tight', dpi=tiff_dpi,
                        pil_kwargs={'compression': 'tiff_lzw'})
            print(f"  Saved: {stem}.png (300 DPI) and tiff/{stem}.tiff ({tiff_dpi} DPI)")
        except Exception as e:
            print(f"  Saved: {stem}.png (300 DPI); TIFF failed ({e}) — install pillow")
    if in_notebook():
        plt.show()
    plt.close(fig)


def png_to_tiff(png_path, dpi=None):
    """Convert a plotly PNG export to TIFF (in tiff/) with DPI metadata."""
    try:
        from PIL import Image
        target = tiff_path(Path(png_path).stem)
        dpi = dpi or config.TIFF_RASTER_DPI
        Image.open(png_path).save(target, dpi=(dpi, dpi), compression='tiff_lzw')
        print(f"  Converted: tiff/{target.name} ({dpi} DPI)")
    except Exception as e:
        print(f"  TIFF conversion failed for {png_path}: {e}")


def save_plotly(fig, filename, width, height, scale=3):
    """Write a plotly figure to PNG (+ TIFF unless disabled) and an interactive HTML copy; shows it in notebooks."""
    path = out_path(filename)
    try:
        fig.write_image(str(path), width=width, height=height, scale=scale)
        print(f"  Saved: {filename}")
        if config.SAVE_TIFF:
            png_to_tiff(path, dpi=config.TIFF_RASTER_DPI)
    except Exception as e:
        print(f"  Could not save {filename}: {e}")
    try:   # interactive copy: zoom/pan/hover in the browser; plotly.min.js is written once next to it
        d = config.OUTPUT_DIR / 'interactive'
        d.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(d / f'{Path(filename).stem}.html'), include_plotlyjs='directory', full_html=True)
    except Exception as e:
        print(f"  Could not save interactive {filename}: {e}")
    if in_notebook():
        fig.show()
