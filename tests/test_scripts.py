"""Repository scripts: docstring rule, README generation, hypothesis consolidation, work log."""
import importlib.util
import json
import subprocess
import sys

import pytest

from conftest import REAL_REPO, git


def load(name):
    """Import scripts/<name>.py as a module."""
    spec = importlib.util.spec_from_file_location(name, REAL_REPO / 'scripts' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_function_has_a_docstring():
    """The pre-commit rule holds for the whole repo right now."""
    check = load('check_docs')
    assert check.missing_docstrings(check.source_files()) == []


def test_check_docs_flags_missing(tmp_path):
    """Modules, functions, classes and methods without docstrings are reported; nested helpers are exempt."""
    check = load('check_docs')
    f = tmp_path / 'm.py'
    f.write_text('def a():\n    def inner():\n        pass\n\nclass B:\n    """ok"""\n    def m(self):\n        pass\n')
    got = check.missing_docstrings([f])
    assert any('<module>' in x for x in got) and any(x.endswith(' a') for x in got) and any('B.m' in x for x in got)
    assert not any('inner' in x for x in got)


def test_readmes_are_current():
    """Committed READMEs match what the generator produces (CI fails if someone forgets to regenerate)."""
    out = subprocess.run([sys.executable, str(REAL_REPO / 'scripts' / 'update_readmes.py'), '--check'],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout


def test_readmes_document_every_function_and_the_data_model():
    """Each source directory README lists every function; db/README has the data model with column usage."""
    gen = load('update_readmes')
    files, edges, runs = gen.scan()
    readmes = gen.build()
    for rel, info in files.items():
        if rel.startswith('src/') and info['funcs']:
            text = readmes[f"{rel.rsplit('/', 1)[0]}/README.md"]
            for sig, doc, _ in info['funcs']:
                assert f'`{sig}`' in text, (rel, sig)
    db = readmes['src/cardiac_imaging/db/README.md']
    assert '## Data model' in db and 'erDiagram' in db and '`Rndrng_Prvdr_RUCA`' in db
    assert 'loaders/claims.py: load_detail' in db


def test_readme_manual_block_survives(tmp_path):
    """Hand-written text inside the MANUAL markers is preserved across regenerations."""
    gen = load('update_readmes')
    old = 'x\n<!-- BEGIN MANUAL -->\nmy notes\n<!-- END MANUAL -->\n'
    assert 'my notes' in gen.with_manual(['# T'], old)


def _transcript(path, messages):
    """Write a minimal Claude Code JSONL transcript with the given user messages."""
    lines = [json.dumps({'type': 'user', 'timestamp': '2026-10-20T10:00:00Z', 'message': {'role': 'user', 'content': m}})
             for m in messages]
    lines.append(json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'content': 'whether CTA rates'}]}}))
    path.write_text('\n'.join(lines))


def test_consolidate_hypotheses(tmp_path, monkeypatch):
    """Chart discussions become tested hypotheses; hypothesis-like Claude Code messages become candidates; secrets redacted."""
    cons = load('consolidate_hypotheses')
    conv_dir, tx_dir, out = tmp_path / 'conv', tmp_path / 'tx', tmp_path / 'out'
    conv_dir.mkdir()
    tx_dir.mkdir()
    (conv_dir / 'c1.json').write_text(json.dumps(dict(
        id='c1', run_id='r1', stem='figure2_market_share', label='Figure 2', title='Market share', started='2026-10-21T09:00:00',
        backend='api', outcome='supported', outcome_note='rural gap persists',
        messages=[dict(role='user', text='Office-based CTA explains the urban growth ghp_FAKEFAKEFAKE'),
                  dict(role='assistant', text='The office share rose in urban segments.')])))
    _transcript(tx_dir / 's.jsonl', ['push to main please',
                                     'I suspect the cardiologist IRR is confounded by state urbanicity',
                                     '<system-reminder>whether CTA density</system-reminder>'])
    monkeypatch.setattr(cons, 'OUT_DIR', out)
    monkeypatch.setattr(sys, 'argv', ['x', '--conversations', str(conv_dir), '--transcripts', str(tx_dir)])
    cons.main()
    md = (out / 'HYPOTHESES.md').read_text()
    assert 'Office-based CTA explains the urban growth [redacted]' in md and '**supported**' in md
    assert 'rural gap persists' in md and 'confounded by state urbanicity' in md
    assert 'push to main' not in md and 'system-reminder' not in md
    data = json.loads((out / 'hypotheses.json').read_text())
    data[0]['notes'] = 'hand note'
    (out / 'hypotheses.json').write_text(json.dumps(data))
    cons.main()
    assert 'hand note' in (out / 'HYPOTHESES.md').read_text()


def test_work_log_entry(tmp_path, monkeypatch):
    """The work-log entry summarises commits, areas touched and functions added/removed; re-running is idempotent."""
    wl = load('work_log')
    from conftest import make_repo
    repo = make_repo(tmp_path / 'r')
    (repo / 'src' / 'cardiac_imaging').mkdir(parents=True)
    (repo / 'src' / 'cardiac_imaging' / 'mod.py').write_text('def old():\n    pass\n')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'add module')
    before = git(repo, 'rev-parse', 'HEAD')
    (repo / 'src' / 'cardiac_imaging' / 'mod.py').write_text('def new():\n    pass\n')
    git(repo, 'commit', '-qam', 'Replace old with new\n\n- Removes old()\n  because it was slow\n- Adds new()')
    after = git(repo, 'rev-parse', 'HEAD')
    monkeypatch.setattr(wl, 'ROOT', repo)
    monkeypatch.setattr(wl, 'LOG', repo / 'docs' / 'WORK_LOG.md')
    text = wl.entry(before, after)
    assert '**Replace old with new**' in text and 'Removes old() because it was slow' in text
    assert 'code: core' in text and 'mod.py: new' in text and 'mod.py: old' in text
    assert wl.prepend(text, after) is True and wl.prepend(text, after) is False
    assert wl.resolve_range('0' * 40, after) == (before, after)


def test_work_log_junit_counts(tmp_path):
    """Test counts are read from a JUnit report."""
    wl = load('work_log')
    f = tmp_path / 'j.xml'
    f.write_text('<testsuites><testsuite tests="10" failures="1" errors="0" skipped="2"/></testsuites>')
    assert wl.test_counts(f) == (7, 1, 2) and wl.test_counts(None) is None
