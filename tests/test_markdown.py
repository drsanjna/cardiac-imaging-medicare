"""Markdown rendering for chat replies: the basic elements render, and nothing in a reply can inject HTML or scripts."""
from cardiac_imaging.app.markdown import render


def test_paragraphs_and_line_breaks():
    """Blank lines separate paragraphs; single newlines become <br>."""
    assert render('one\ntwo\n\nthree') == '<p>one<br>two</p>\n<p>three</p>'


def test_inline_formatting():
    """Bold, italic, strikethrough and inline code."""
    out = render('**b** __b2__ *i* _i2_ ~~s~~ `x = a*b*c`')
    assert '<strong>b</strong>' in out and '<strong>b2</strong>' in out
    assert '<em>i</em>' in out and '<em>i2</em>' in out and '<del>s</del>' in out
    assert '<code>x = a*b*c</code>' in out          # no emphasis inside code


def test_snake_case_and_arithmetic_are_not_emphasis():
    """Identifiers like fit_density_models and expressions like 2 * 3 * 4 stay literal."""
    out = render('fit_density_models uses rate_per_1000; 2 * 3 * 4')
    assert '<em>' not in out and 'fit_density_models' in out


def test_headings_are_chat_sized():
    """# → h3 … #### → h6 (capped)."""
    assert render('# A') == '<h3>A</h3>' and render('### C') == '<h5>C</h5>' and render('##### E') == '<h6>E</h6>'


def test_lists_nested_and_ordered():
    """Bulleted, numbered and nested lists, including wrapped continuation lines."""
    out = render('- one\n  continued\n  - nested\n- two\n\n1. first\n2) second')
    assert out.startswith('<ul><li>one continued<ul><li>nested</li></ul></li><li>two</li></ul>')
    assert '<ol><li>first</li><li>second</li></ol>' in out


def test_code_block_is_escaped_and_tagged():
    """Fenced code keeps its content verbatim (escaped) with a language class."""
    out = render('```python\nif a < b and c > d:\n    print("**not bold**")\n```')
    assert out == ('<pre><code class="language-python">if a &lt; b and c &gt; d:\n'
                   '    print(&quot;**not bold**&quot;)</code></pre>')


def test_unclosed_code_block_runs_to_end():
    """A missing closing fence still renders everything after it as code."""
    assert render('```\nx\ny').startswith('<pre><code>x\ny')


def test_table():
    """Pipe tables with a separator row become HTML tables; inline formatting works in cells."""
    out = render('| Model | IRR |\n|:---|---:|\n| All | **1.188** |\n| Rad | 1.231 |')
    assert '<th>Model</th><th>IRR</th>' in out and '<td>All</td><td><strong>1.188</strong></td>' in out
    assert out.count('<tr>') == 3


def test_blockquote_and_rule():
    """Quotes (may contain other Markdown) and horizontal rules."""
    assert render('> **note**\n> more') == '<blockquote><p><strong>note</strong><br>more</p></blockquote>'
    assert render('a\n\n---\n\nb') == '<p>a</p>\n<hr>\n<p>b</p>'


def test_links_safe_and_unsafe():
    """http(s)/mailto/relative links become anchors; javascript: and data: links stay plain text; URLs aren't mangled."""
    out = render('[docs](https://x.org/a_b_c_d.html) [mail](mailto:a@b.c) [rel](./x.md)')
    assert '<a href="https://x.org/a_b_c_d.html" target="_blank" rel="noopener noreferrer">docs</a>' in out
    assert 'href="mailto:a@b.c"' in out and 'href="./x.md"' in out
    for bad in ('javascript:alert(1)', 'data:text/html,hi', 'JaVaScRiPt:alert(1)'):
        assert '<a ' not in render(f'[x]({bad})')


def test_html_and_scripts_are_never_executed():
    """Raw HTML in a reply is escaped wherever it appears — text, headings, lists, tables, quotes, link text."""
    payloads = ['<script>alert(1)</script>', '<img src=x onerror=alert(1)>', '"><svg onload=alert(1)>']
    for p in payloads:
        for md in (p, f'# {p}', f'- {p}', f'| a |\n|---|\n| {p} |', f'> {p}', f'[{p}](https://x.org)', f'**{p}**'):
            out = render(md)
            assert '<script' not in out and '<img' not in out and '<svg' not in out, (md, out)


def test_link_url_cannot_break_out_of_attribute():
    """Quotes in a URL are escaped, so they can't add attributes."""
    out = render('[x](https://a.org/"onmouseover="alert(1))')
    assert 'onmouseover="' not in out


def test_empty_and_none():
    """Empty input renders to an empty string."""
    assert render('') == '' and render(None) == ''
