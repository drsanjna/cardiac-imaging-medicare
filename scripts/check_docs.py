"""Fail if any module, function, method or class in src/, scripts/ or tests/ lacks a docstring (READMEs explain every function).

    python scripts/check_docs.py        # exit 1 and list what is missing
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def missing_docstrings(paths):
    """['file:line name', ...] for every module/class/function (incl. methods and private helpers) without a docstring.

    Functions nested inside other functions are exempt (they're explained by their parent).
    """
    out = []
    for p in paths:
        tree = ast.parse(p.read_text())
        rel = p.relative_to(ROOT) if p.is_relative_to(ROOT) else p
        if not ast.get_docstring(tree):
            out.append(f"{rel}:1 <module>")

        def visit(nodes, prefix=''):
            for n in nodes:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    if not ast.get_docstring(n):
                        out.append(f"{rel}:{n.lineno} {prefix}{n.name}")
                    if isinstance(n, ast.ClassDef):
                        visit(n.body, f'{n.name}.')
        visit(tree.body)
    return out


def source_files():
    """Every .py file in src/, scripts/ and tests/."""
    return sorted((ROOT / 'src').rglob('*.py')) + sorted((ROOT / 'scripts').glob('*.py')) + sorted((ROOT / 'tests').glob('*.py'))


def main():
    """Print missing docstrings and exit 1 if there are any."""
    missing = missing_docstrings(source_files())
    if missing:
        print("Every function needs a one-line docstring (it becomes its README explanation). Missing:")
        print('\n'.join(f'  {m}' for m in missing))
        sys.exit(1)
    print(f"Docstrings OK ({len(source_files())} files).")


if __name__ == '__main__':
    main()
