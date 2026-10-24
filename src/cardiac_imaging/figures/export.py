"""Save figures to OUTPUT_DIR as PNG (300 DPI) + LZW TIFF, and display them only inside notebooks."""
import matplotlib.pyplot as plt

from .. import config


def in_notebook():
    try:
        from IPython import get_ipython
        return get_ipython() is not None and 'IPKernelApp' in get_ipython().config
    except Exception:
        return False


def out_path(name):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return config.OUTPUT_DIR / name


def save_pub_fig(fig, stem, tiff_dpi):
    """Save a matplotlib figure as working PNG (300 DPI) + submission TIFF (LZW), then show/close it."""
    stem = out_path(stem)
    fig.savefig(f'{stem}.png', bbox_inches='tight', dpi=300)
    try:
        fig.savefig(f'{stem}.tiff', bbox_inches='tight', dpi=tiff_dpi,
                    pil_kwargs={'compression': 'tiff_lzw'})
        print(f"  Saved: {stem.name}.png (300 DPI) and {stem.name}.tiff ({tiff_dpi} DPI)")
    except Exception as e:
        print(f"  Saved: {stem.name}.png (300 DPI); TIFF failed ({e}) — install pillow")
    if in_notebook():
        plt.show()
    plt.close(fig)


def png_to_tiff(png_path, dpi=config.TIFF_RASTER_DPI):
    """Convert a plotly PNG export to TIFF with DPI metadata."""
    try:
        from PIL import Image
        tiff_path = str(png_path).rsplit('.', 1)[0] + '.tiff'
        Image.open(png_path).save(tiff_path, dpi=(dpi, dpi), compression='tiff_lzw')
        print(f"  Converted: {tiff_path} ({dpi} DPI)")
    except Exception as e:
        print(f"  TIFF conversion failed for {png_path}: {e}")


def save_plotly(fig, filename, width, height, scale=3):
    """Write a plotly figure to PNG + TIFF; shows it in notebooks."""
    path = out_path(filename)
    try:
        fig.write_image(str(path), width=width, height=height, scale=scale)
        print(f"  Saved: {filename}")
        png_to_tiff(path, dpi=config.TIFF_RASTER_DPI)
    except Exception as e:
        print(f"  Could not save {filename}: {e}")
    if in_notebook():
        fig.show()
