"""Safe Markdown → HTML for chat replies: headings, bold/italic, code, lists, links, quotes, tables, rules (escape-first, no raw HTML)."""
import html
import re

_LINK = re.compile(r'\[([^\]\n]+)\]\(([^)\s]+)\)')
_SAFE_URL = re.compile(r'^(https?://|mailto:|/|\./|\.\./|#)', re.I)
_FENCE = re.compile(r'^\s*(```|~~~)\s*([\w+-]*)\s*$')
_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*#*\s*$')
_LIST = re.compile(r'^(\s*)([-*+]|\d+[.)])\s+(.*)$')
_RULE = re.compile(r'^\s*([-*_])(\s*\1){2,}\s*$')
_TABLE_SEP = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$')


def _inline(text):
    """Inline formatting on one line of text: `code`, **bold**, *italic*/_italic_, ~~strike~~ and [links](url)."""
    parts = re.split(r'(`[^`\n]+`)', text)
    out = []
    for part in parts:
        if len(part) > 1 and part.startswith('`') and part.endswith('`'):
            out.append(f'<code>{html.escape(part[1:-1])}</code>')
            continue
        s = html.escape(part, quote=True)
        links = []

        def stash(m):
            """Swap a safe link for a placeholder so emphasis rules can't touch its URL."""
            if not _SAFE_URL.match(html.unescape(m.group(2))):
                return m.group(0)
            links.append((m.group(2), _emphasis(m.group(1))))
            return f'\x00{len(links) - 1}\x00'
        s = _emphasis(_LINK.sub(stash, s))
        s = re.sub('\x00(\\d+)\x00', lambda m: '<a href="{0}" target="_blank" rel="noopener noreferrer">{1}</a>'
                   .format(*links[int(m.group(1))]), s)
        out.append(s)
    return ''.join(out)


def _emphasis(s):
    """**bold**, __bold__, *italic*, _italic_ and ~~strike~~ on already-escaped text (snake_case is left alone)."""
    s = re.sub(r'\*\*(?=\S)(.+?)(?<=\S)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'__(?=\S)(.+?)(?<=\S)__', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])', r'<em>\1</em>', s)
    s = re.sub(r'(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])', r'<em>\1</em>', s)
    return re.sub(r'~~(?=\S)(.+?)(?<=\S)~~', r'<del>\1</del>', s)


def _cells(row):
    """Cells of a Markdown table row (outer pipes optional)."""
    row = row.strip()
    if row.startswith('|'):
        row = row[1:]
    if row.endswith('|'):
        row = row[:-1]
    return [c.strip() for c in row.split('|')]


def _list_html(items):
    """Nested <ul>/<ol> from [(indent, ordered, text)] items."""
    out, stack = [], []          # stack of (indent, tag)
    for indent, ordered, text in items:
        tag = 'ol' if ordered else 'ul'
        while stack and indent < stack[-1][0]:
            out.append(f'</li></{stack.pop()[1]}>')
        if not stack or indent > stack[-1][0]:
            out.append(f'<{tag}>')
            stack.append((indent, tag))
        else:
            out.append('</li>')
        out.append(f'<li>{_inline(text)}')
    while stack:
        out.append(f'</li></{stack.pop()[1]}>')
    return ''.join(out)


def render(text):
    """Convert Markdown text to HTML. All input is escaped first, so raw HTML/scripts in the text are shown, never run."""
    lines = (text or '').replace('\r\n', '\n').replace('\r', '\n').split('\n')
    out, para, i = [], [], 0

    def flush():
        """Emit the paragraph collected so far."""
        if para:
            out.append('<p>' + '<br>'.join(_inline(x) for x in para) + '</p>')
            para.clear()

    while i < len(lines):
        line = lines[i]
        fence = _FENCE.match(line)
        if fence:
            flush()
            lang, body, i = fence.group(2), [], i + 1
            while i < len(lines) and not _FENCE.match(lines[i]):
                body.append(lines[i])
                i += 1
            cls = f' class="language-{html.escape(lang)}"' if lang else ''
            out.append(f'<pre><code{cls}>{html.escape(chr(10).join(body))}</code></pre>')
            i += 1
            continue
        if not line.strip():
            flush()
            i += 1
            continue
        heading = _HEADING.match(line)
        if heading:
            flush()
            level = min(len(heading.group(1)) + 2, 6)          # chat-sized: # → h3 … ### → h5
            out.append(f'<h{level}>{_inline(heading.group(2))}</h{level}>')
            i += 1
            continue
        if _RULE.match(line):
            flush()
            out.append('<hr>')
            i += 1
            continue
        if '|' in line and i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1]):
            flush()
            head = _cells(line)
            rows, i = [], i + 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                rows.append(_cells(lines[i]))
                i += 1
            th = ''.join(f'<th>{_inline(c)}</th>' for c in head)
            body = ''.join('<tr>' + ''.join(f'<td>{_inline(c)}</td>' for c in r[:len(head)]) + '</tr>' for r in rows)
            out.append(f'<div class="md-table"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>')
            continue
        if line.lstrip().startswith('>'):
            flush()
            quote = []
            while i < len(lines) and lines[i].lstrip().startswith('>'):
                quote.append(re.sub(r'^\s*>\s?', '', lines[i]))
                i += 1
            out.append(f'<blockquote>{render(chr(10).join(quote))}</blockquote>')
            continue
        if _LIST.match(line):
            flush()
            items = []
            while i < len(lines):
                m = _LIST.match(lines[i])
                if m:
                    items.append((len(m.group(1).replace('\t', '    ')), not m.group(2)[0] in '-*+', m.group(3)))
                elif lines[i].strip() and items and lines[i].startswith((' ', '\t')):
                    ind, ordered, txt = items[-1]
                    items[-1] = (ind, ordered, f'{txt} {lines[i].strip()}')   # wrapped continuation line
                else:
                    break
                i += 1
            out.append(_list_html(items))
            continue
        para.append(line)
        i += 1
    flush()
    return '\n'.join(out)
