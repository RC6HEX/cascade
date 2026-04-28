"""Unit tests for the multi-file LLM output parser."""
from __future__ import annotations

import pytest

from generator.parser import parse_files, parse_files_strict


def test_parses_single_file():
    text = """### FILE: src/index.html
```html
<!DOCTYPE html>
<html><body>hi</body></html>
```
"""
    files = parse_files(text)
    assert set(files) == {"src/index.html"}
    assert "<!DOCTYPE html>" in files["src/index.html"]


def test_parses_multiple_files():
    text = """### FILE: src/app.js
```javascript
export const hi = 1;
```

### FILE: src/styles.css
```css
body { color: red; }
```

### FILE: src/index.html
```html
<html></html>
```
"""
    files = parse_files(text)
    assert set(files) == {"src/app.js", "src/styles.css", "src/index.html"}
    assert "export const hi" in files["src/app.js"]
    assert "color: red" in files["src/styles.css"]


def test_tolerates_h2_h4_headers():
    text = """## FILE: a.js
```javascript
1
```
#### FILE: b.js
```javascript
2
```
"""
    files = parse_files(text)
    assert set(files) == {"a.js", "b.js"}


def test_tolerates_no_language_tag():
    text = """### FILE: foo.txt
```
plain text
```
"""
    files = parse_files(text)
    assert files["foo.txt"].strip() == "plain text"


def test_skips_empty_bodies():
    text = """### FILE: empty.txt
```
```
### FILE: full.txt
```
content
```
"""
    files = parse_files(text)
    assert "empty.txt" not in files
    assert "full.txt" in files


def test_normalizes_paths():
    text = """### FILE: /src/foo.js
```javascript
1
```
### FILE: src\\bar.js
```javascript
2
```
"""
    files = parse_files(text)
    # Leading slash stripped, backslashes normalized
    assert "src/foo.js" in files
    assert "src/bar.js" in files


def test_strict_raises_when_no_files():
    with pytest.raises(ValueError, match="No files found"):
        parse_files_strict("just some text without file markers")


def test_strict_returns_when_files_present():
    text = """### FILE: x.js
```javascript
1
```
"""
    files = parse_files_strict(text)
    assert files == {"x.js": "1\n"}


def test_handles_code_blocks_with_inner_backticks():
    text = """### FILE: snippet.md
```markdown
Use `npm install` to install.
And here's a code sample:

    const x = 1;
```
"""
    files = parse_files(text)
    assert "snippet.md" in files
    assert "npm install" in files["snippet.md"]


def test_dedup_keeps_last():
    text = """### FILE: a.js
```javascript
first
```
### FILE: a.js
```javascript
second
```
"""
    files = parse_files(text)
    assert files["a.js"].strip() == "second"
