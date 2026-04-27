"""Parse multi-file LLM output into a {path: content} dict."""
from __future__ import annotations

import re

# Format the LLM is instructed to produce:
#
# ### FILE: src/index.html
# ```html
# ...content...
# ```
#
# ### FILE: src/app.js
# ```javascript
# ...content...
# ```
#
# We tolerate variations: "FILE:", "File:", optional spaces, optional language tag.

_FILE_RE = re.compile(
    r"""(?im)
    ^[ \t]*\#{1,6}[ \t]*FILE:[ \t]*(?P<path>[\w./\-+@]+)[ \t]*$
    \s*```(?P<lang>[\w+\-]*)\s*\n
    (?P<body>.*?)
    \n```[ \t]*$
    """,
    re.VERBOSE | re.DOTALL,
)


def parse_files(text: str) -> dict[str, str]:
    """Extract files from LLM markdown output.

    Returns dict {relative_path: content}.
    Skips empty bodies and dedups by path (later occurrence wins).
    """
    files: dict[str, str] = {}
    for m in _FILE_RE.finditer(text):
        path = m.group("path").strip().lstrip("/").replace("\\", "/")
        body = m.group("body")
        if not path or not body.strip():
            continue
        # Normalize trailing whitespace, ensure single trailing newline
        body = body.rstrip() + "\n"
        files[path] = body
    return files


def parse_files_strict(text: str) -> dict[str, str]:
    """Like parse_files but raises if no files found."""
    files = parse_files(text)
    if not files:
        snippet = text[:600].replace("\n", "\\n")
        raise ValueError(
            f"No files found in LLM output. Expected '### FILE: <path>' headers. "
            f"First 600 chars: {snippet}"
        )
    return files
