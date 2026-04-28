"""Parse multi-file LLM output into a {path: content} dict.

The LLM is instructed to produce blocks like:

    ### FILE: src/index.html
    ```html
    ...content...
    ```

    ### FILE: src/app.js
    ```javascript
    ...
    ```

We tolerate variations:
- Header level (1–6 hashes).
- "FILE:" / "File:" / "file:" — case insensitive on the keyword.
- Optional language tag after the fence.
- Backslashes in paths (normalized to /).
- Leading slash in paths (stripped).
- Empty bodies (skipped).
"""
from __future__ import annotations

import re

# Match a file header line. Use as a splitter, not a single big regex —
# this avoids cross-file backtracking issues (where a non-greedy body would
# accidentally consume a second header).
_HEADER_RE = re.compile(
    r"^[ \t]*\#{1,6}[ \t]*FILE:[ \t]*(?P<path>[\w./\-+@\\]+)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

# Within one file's chunk, find the first fenced code block.
_CODE_BLOCK_RE = re.compile(
    r"```(?P<lang>[\w+\-]*)\s*\n(?P<body>.*?)\n[ \t]*```",
    re.DOTALL,
)


def _normalize_path(p: str) -> str:
    return p.strip().lstrip("/").replace("\\", "/")


def parse_files(text: str) -> dict[str, str]:
    """Extract files from LLM markdown output.

    Returns dict {relative_path: content}.
    Skips empty bodies. Later occurrences of the same path overwrite earlier.
    """
    files: dict[str, str] = {}
    headers = list(_HEADER_RE.finditer(text))
    if not headers:
        return files

    for i, m in enumerate(headers):
        path = _normalize_path(m.group("path"))
        if not path:
            continue
        # Slice between this header's end and the next header's start.
        chunk_start = m.end()
        chunk_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        chunk = text[chunk_start:chunk_end]

        cb = _CODE_BLOCK_RE.search(chunk)
        if not cb:
            continue
        body = cb.group("body")
        if not body.strip():
            continue
        # Normalize trailing whitespace, ensure a single trailing newline.
        files[path] = body.rstrip() + "\n"
    return files


def parse_files_strict(text: str) -> dict[str, str]:
    """Like parse_files but raises if no files were found."""
    files = parse_files(text)
    if not files:
        snippet = text[:600].replace("\n", "\\n")
        raise ValueError(
            f"No files found in LLM output. Expected '### FILE: <path>' headers. "
            f"First 600 chars: {snippet}"
        )
    return files
