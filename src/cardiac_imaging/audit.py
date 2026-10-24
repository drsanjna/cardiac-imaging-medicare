"""Integrity log: every filter prints what it kept and dropped, so no rows disappear silently."""

FILTER_LOG = []   # one dict per filter applied in the current run (saved to the run's tables/)


def log_filter(label, before, after, unit='rows', dropped_items=None):
    """Print '[filter] label: before → after unit (n dropped)', record it in FILTER_LOG, and return `after`."""
    dropped = sorted(dropped_items) if dropped_items else []
    FILTER_LOG.append(dict(filter=label, before=int(before), after=int(after),
                           dropped=int(before) - int(after), unit=unit, dropped_items=', '.join(map(str, dropped))))
    extra = f": {dropped}" if dropped else ''
    print(f"  [filter] {label}: {before:,} → {after:,} {unit} ({before - after:,} dropped{extra})")
    return after
