---
paths:
  - "packages/**/*.py"
  - "services/**/*.py"
---

# Python import rules

- Do not use `from __future__ import annotations`. The project requires Python 3.13, so annotations
  must use the runtime's native behavior and syntax.
- Use absolute import paths. Both `import package.module` and
  `from package.module import Member` are allowed.
- Do not use relative imports such as `from .module import Member` or
  `from ..package import Member`.
- Apply the same convention to production code, package tests, and Python examples documenting
  these packages and services.
