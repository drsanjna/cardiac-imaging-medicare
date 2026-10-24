"""Sync runs between your laptops through GitHub: upload what's missing, download what's new, repair incomplete releases.

    python scripts/sync_runs.py               # sync now (safe to run any time, on either laptop)
    python scripts/sync_runs.py --dry-run     # show what would happen
    python scripts/sync_runs.py --check       # verify only; exit 1 if anything is out of sync (good for scripts)
    python scripts/sync_runs.py --install-schedule 30   # also sync automatically every 30 minutes (macOS LaunchAgent)
    python scripts/sync_runs.py --uninstall-schedule
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cardiac_imaging import config  # noqa: E402
from cardiac_imaging.reporting import sync  # noqa: E402

LABEL = 'com.cardiac-imaging.sync-runs'
PLIST = Path.home() / 'Library' / 'LaunchAgents' / f'{LABEL}.plist'
LOG = Path.home() / 'Library' / 'Logs' / 'cardiac-imaging-sync.log'


def plist_text(minutes):
    """LaunchAgent definition that runs this script every `minutes` minutes with the current Python."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>{LABEL}</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string><string>{ROOT / 'scripts' / 'sync_runs.py'}</string></array>
  <key>WorkingDirectory</key><string>{ROOT}</string>
  <key>StartInterval</key><integer>{int(minutes) * 60}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{LOG}</string>
  <key>StandardErrorPath</key><string>{LOG}</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string></dict>
</dict></plist>
"""


def install_schedule(minutes):
    """Write and load the LaunchAgent (replacing an existing one)."""
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['launchctl', 'unload', str(PLIST)], capture_output=True)
    PLIST.write_text(plist_text(minutes))
    subprocess.run(['launchctl', 'load', str(PLIST)], check=True)
    print(f"Automatic sync every {minutes} min installed ({PLIST}); log: {LOG}")


def uninstall_schedule():
    """Unload and remove the LaunchAgent if present."""
    if PLIST.exists():
        subprocess.run(['launchctl', 'unload', str(PLIST)], capture_output=True)
        PLIST.unlink()
        print('Automatic sync removed.')
    else:
        print('No automatic sync was installed.')


def main():
    """Parse options and sync, check, or manage the schedule."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true', help='report what would happen; change nothing')
    ap.add_argument('--check', action='store_true', help="verify only (no uploads/downloads); exit 1 if out of sync")
    ap.add_argument('--no-download', action='store_true', help="don't download runs that are only on GitHub")
    ap.add_argument('--install-schedule', type=int, metavar='MINUTES', help='sync automatically every N minutes')
    ap.add_argument('--uninstall-schedule', action='store_true')
    args = ap.parse_args()
    if args.install_schedule:
        return install_schedule(args.install_schedule)
    if args.uninstall_schedule:
        return uninstall_schedule()
    print(f"Syncing runs in {config.RUNS_DIR} with GitHub …")
    report = sync.sync(upload=not args.check, download=not (args.check or args.no_download),
                       dry_run=args.dry_run or args.check)
    print(sync.summarize(report))
    bad = [r for r in report if r['action'] not in ('ok', 'on GitHub only', 'label ← GitHub', 'uploaded',
                                                    'downloaded', 'repaired')]
    if args.check and bad:
        print(f"{len(bad)} run(s) out of sync — run: python scripts/sync_runs.py")
        sys.exit(1)
    if any(r['action'].endswith('failed') for r in report):
        sys.exit(1)


if __name__ == '__main__':
    main()
