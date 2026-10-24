"""Integrity log: every filter prints what it kept and dropped, so no rows disappear silently."""


def log_filter(label, before, after, unit='rows', dropped_items=None):
    """Print '[filter] label: before → after unit (n dropped)' and return `after`."""
    extra = f": {sorted(dropped_items)}" if dropped_items else ''
    print(f"  [filter] {label}: {before:,} → {after:,} {unit} ({before - after:,} dropped{extra})")
    return after
