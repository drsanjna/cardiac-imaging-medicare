"""Consolidate project conversations into a log of hypotheses and how they were tested: docs/hypotheses/.

Sources
  1. Chart discussions from the local app (~/Downloads/cms_conversations/*.json) — each is one hypothesis with the
     outcome you set (supported / not supported / inconclusive / open) and Claude's last answer.
  2. Claude Code conversations on this project (~/.claude/projects/<this repo>/*.jsonl) — your messages that propose
     or question a hypothesis are listed as candidates.

    python scripts/consolidate_hypotheses.py            # update docs/hypotheses/HYPOTHESES.md + hypotheses.json
    python scripts/consolidate_hypotheses.py --dry-run  # print what would be written

The repo is public: only short hypothesis statements are stored (never whole conversations), and token-like strings
are redacted. Edit `status_override` / `notes` in hypotheses.json by hand — they are kept on every re-run.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from cardiac_imaging import config  # noqa: E402

OUT_DIR = ROOT / 'docs' / 'hypotheses'
MAX_LEN = 400
SECRET = re.compile(r'(ghp_|github_pat_|sk-ant-|AKIA|xox[bp]-)[A-Za-z0-9_\-]{8,}')
TAGS = re.compile(r'<(system-reminder|command-[a-z-]+|local-command-[a-z-]+|task-notification|pasted_content)[^>]*>.*?</\1>', re.S)
HYPOTHESIS = re.compile(r"\bhypothes|\bi (think|suspect|wonder|bet)\b|\bwhether\b|\bcould (it|this) be\b|\bis (it|this|that) "
                        r"(because|due to|driven)|\b(driven by|explained by|associated with|correlat\w*|confound\w*)\b|"
                        r"\bdoes \w+.{0,60}\b(affect|explain|drive|predict|differ)", re.I)
DOMAIN = re.compile(r"\b(cta|echo|spect|pet|mri|cmr|imaging|densit\w*|utili[sz]ation|rates?|states?|rural|urban|radiolog\w*|"
                    r"cardiolog\w*|irr|medicare|ffs|enrollment|npi|physicians?|modalit\w*|market share|office|facility)\b", re.I)


def clean(text):
    """Strip app/system wrappers, collapse whitespace, redact secrets, cap the length."""
    text = TAGS.sub(' ', text or '')
    text = SECRET.sub('[redacted]', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if len(text) <= MAX_LEN else text[:MAX_LEN - 1].rstrip() + '…'


def rid(*parts):
    """Stable id for a hypothesis record."""
    return hashlib.sha1('|'.join(parts).encode()).hexdigest()[:10]


def from_chart_discussions(conv_dir):
    """One record per saved chart discussion (the first message is the hypothesis)."""
    out = []
    for p in sorted(Path(conv_dir).glob('*.json')):
        try:
            c = json.loads(p.read_text())
        except ValueError:
            continue
        users = [m for m in c.get('messages', []) if m.get('role') == 'user']
        if not users:
            continue
        answers = [m for m in c.get('messages', []) if m.get('role') == 'assistant' and not m.get('text', '').startswith('⚠️')]
        out.append(dict(id=rid('chart', c['id']), source='chart discussion', hypothesis=clean(users[0]['text']),
                        chart=f"{c.get('label')} — {c.get('title')}", run=c.get('run_id'), date=c.get('started', '')[:10],
                        status=c.get('outcome', 'open').replace('_', ' '), note=clean(c.get('outcome_note', '')),
                        follow_ups=len(users) - 1,
                        conclusion=clean(answers[-1]['text']) if answers and c.get('backend') != 'handoff' else ''))
    return out


def user_texts(transcript):
    """(timestamp, text) for each message the user typed in a Claude Code transcript (tool results and wrappers skipped)."""
    out = []
    for line in Path(transcript).read_text(errors='ignore').splitlines():
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get('type') != 'user' or d.get('isMeta'):
            continue
        content = (d.get('message') or {}).get('content')
        if isinstance(content, list):
            if any(b.get('type') == 'tool_result' for b in content if isinstance(b, dict)):
                continue
            content = ' '.join(b.get('text', '') for b in content if isinstance(b, dict) and b.get('type') == 'text')
        text = clean(content if isinstance(content, str) else '')
        if text:
            out.append((d.get('timestamp', ''), text))
    return out


def from_claude_code(transcript_dir):
    """Candidate hypotheses: user messages in this project's Claude Code sessions that propose or question an effect."""
    out = []
    for p in sorted(Path(transcript_dir).glob('*.jsonl')):
        for ts, text in user_texts(p):
            if HYPOTHESIS.search(text) and DOMAIN.search(text):
                out.append(dict(id=rid('claude-code', p.stem, text), source='Claude Code session', hypothesis=text,
                                chart='', run='', date=ts[:10], status='candidate (not yet tested)', note='',
                                follow_ups=0, conclusion=''))
    return out


def transcripts_dir():
    """~/.claude/projects/<repo path with / → ->, where Claude Code stores this project's conversations."""
    return Path.home() / '.claude' / 'projects' / str(config.REPO_ROOT).replace('/', '-')


def merge(new, old):
    """Keep hand-edited fields (status_override, notes) from the previous hypotheses.json."""
    prev = {r['id']: r for r in old}
    for r in new:
        for k in ('status_override', 'notes'):
            if prev.get(r['id'], {}).get(k):
                r[k] = prev[r['id']][k]
    return new


def render(records, n_conv, n_sessions):
    """HYPOTHESES.md content."""
    def status(r):
        return r.get('status_override') or r['status']
    tested = [r for r in records if r['source'] == 'chart discussion']
    cands = [r for r in records if r['source'] != 'chart discussion']
    counts = {}
    for r in tested:
        counts[status(r)] = counts.get(status(r), 0) + 1
    lines = ['# Hypotheses log', '',
             f"Consolidated {datetime.now():%Y-%m-%d} from {n_conv} chart discussion(s) and {n_sessions} Claude Code session(s) "
             'by `scripts/consolidate_hypotheses.py`. Edit `status_override` / `notes` in `hypotheses.json` to correct an entry.', '']
    lines += ['## Tested through chart discussions', '']
    if tested:
        lines += ['Tally: ' + ', '.join(f'{k}: {v}' for k, v in sorted(counts.items())), '',
                  '| Date | Chart | Hypothesis | Outcome | What was concluded |', '|---|---|---|---|---|']
        for r in sorted(tested, key=lambda r: r['date'], reverse=True):
            concl = ' '.join(x for x in [r.get('notes') or r['note'], r['conclusion']] if x) or '—'
            lines.append(f"| {r['date']} | {r['chart']} | {r['hypothesis']} | **{status(r)}** | {concl} |")
    else:
        lines.append('None yet — open a run gallery from the app and click **💬 Discuss a hypothesis** on a chart.')
    lines += ['', '## Candidates raised in Claude Code conversations', '']
    if cands:
        lines += ['| Date | Hypothesis | Status |', '|---|---|---|']
        lines += [f"| {r['date']} | {r['hypothesis']} | {status(r)} |" for r in sorted(cands, key=lambda r: r['date'], reverse=True)]
    else:
        lines.append('None found so far (conversations have been about building the pipeline).')
    return '\n'.join(lines) + '\n'


def main():
    """Collect, merge and write the hypotheses log (or print it with --dry-run)."""
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--conversations', type=Path, default=config.CONVERSATIONS_DIR)
    ap.add_argument('--transcripts', type=Path, default=None)
    args = ap.parse_args()
    tdir = args.transcripts or transcripts_dir()
    chart_recs = from_chart_discussions(args.conversations)
    cc_recs = from_claude_code(tdir)
    old_json = OUT_DIR / 'hypotheses.json'
    old = json.loads(old_json.read_text()) if old_json.exists() else []
    records = merge(chart_recs + cc_recs, old)
    md = render(records, len(list(Path(args.conversations).glob('*.json'))), len(list(Path(tdir).glob('*.jsonl'))))
    if args.dry_run:
        print(md)
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    old_json.write_text(json.dumps(records, indent=2) + '\n')
    (OUT_DIR / 'HYPOTHESES.md').write_text(md)
    shown = OUT_DIR.relative_to(ROOT) if OUT_DIR.is_relative_to(ROOT) else OUT_DIR
    print(f"Wrote {len(chart_recs)} tested + {len(cc_recs)} candidate hypotheses to {shown}/")


if __name__ == '__main__':
    main()
