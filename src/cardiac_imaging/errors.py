"""Capture pipeline failures: write logs/last_error.md and (optionally) open a GitHub issue that tags @claude."""
import json
import os
import platform
import traceback
import urllib.request
from datetime import datetime, timezone

from . import config
from .gitinfo import git as _git, repo_slug as _repo_slug

ISSUE_LABEL = 'notebook-error'


def format_report(exc, step):
    """Markdown error report: failing step, exception, commit, time, Python version and traceback."""
    tb = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return (
        f"## Pipeline step failed: `{step}`\n\n"
        f"- **Error:** `{type(exc).__name__}: {exc}`\n"
        f"- **Commit:** `{_git('rev-parse', '--short', 'HEAD') or 'unknown'}`\n"
        f"- **When:** {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}\n"
        f"- **Python:** {platform.python_version()} on {platform.system()}\n\n"
        f"```text\n{tb}```\n"
    )


def _github(method, url, token, payload=None):
    """Call the GitHub REST API with a token and return the decoded JSON."""
    req = urllib.request.Request(
        url, method=method, data=json.dumps(payload).encode() if payload else None,
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read() or 'null')


def open_issue(title, body):
    """Open (or comment on an existing open) issue labeled notebook-error. Needs CARDIAC_GITHUB_TOKEN."""
    token, slug = os.environ.get('CARDIAC_GITHUB_TOKEN'), _repo_slug()
    if not token or not slug:
        print("  (No CARDIAC_GITHUB_TOKEN / repo — skipped GitHub issue.)")
        return None
    api = f'https://api.github.com/repos/{slug}/issues'
    body += ("\n---\n@claude This error came from running `notebooks/main.ipynb`. "
             "Find the root cause in `src/cardiac_imaging/`, fix it, and open a PR. "
             "Do not change analysis definitions in `config.py` unless the error requires it.")
    try:
        existing = [i for i in _github('GET', f'{api}?labels={ISSUE_LABEL}&state=open', token)
                    if i['title'] == title]
        if existing:
            _github('POST', f"{api}/{existing[0]['number']}/comments", token, {'body': body})
            print(f"  Commented on existing issue: {existing[0]['html_url']}")
            return existing[0]['html_url']
        issue = _github('POST', api, token, {'title': title, 'body': body, 'labels': [ISSUE_LABEL]})
        print(f"  Opened GitHub issue for Claude: {issue['html_url']}")
        return issue['html_url']
    except Exception as e:
        print(f"  Could not open GitHub issue ({e}).")
        return None


def report(exc, step):
    """Write logs/last_error.md and, unless CARDIAC_REPORT_ERRORS=0, open a GitHub issue."""
    body = format_report(exc, step)
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    (config.LOG_DIR / 'last_error.md').write_text(body)
    print(f"\n✖ Step '{step}' failed. Details: {config.LOG_DIR / 'last_error.md'}")
    if os.environ.get('CARDIAC_REPORT_ERRORS', '1') != '0':
        open_issue(f"Notebook error in {step}: {type(exc).__name__}", body)
