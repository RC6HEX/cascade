"""Build cascade.pdf — 20-slide presentation about the Cascade project.

Pure Python via reportlab. No LibreOffice / Office dependency.
Run:
    python presentation/build_pdf.py
Output:
    presentation/cascade.pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# === Page geometry: 16:9 landscape, 13.33" x 7.5" (matches 1920x1080 ratio) ===
PAGE = (13.333 * inch, 7.5 * inch)
W, H = PAGE

# Maximum y for any content card on slides with page_header (subtitle baseline ~5.55,
# minus glyph height + margin → safe ceiling at 5.15"). Cards' top edge MUST be ≤ this.
CONTENT_TOP = 5.15 * inch

# === Cascade design tokens ===
BG = HexColor("#08080d")
BG_2 = HexColor("#14141f")
BG_3 = HexColor("#1c1c2a")
BORDER = HexColor("#232333")
FG = HexColor("#f5f5fa")
FG_2 = HexColor("#c2c2d4")
MUTED = HexColor("#7a7a92")
ACCENT = HexColor("#7c5cff")          # purple
ACCENT_2 = HexColor("#3a86ff")        # blue
ACCENT_3 = HexColor("#3acf7e")        # green
WARN = HexColor("#ffaa00")
DANGER = HexColor("#ff5252")

# Try registering a Unicode-capable font (Cyrillic + emoji-like).
# Falls back to Helvetica if none found.
FONT_REG = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_MONO = "Courier"
for name, paths in (
    ("Inter", [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]),
    ("Inter-Bold", [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]),
    ("Mono", [
        r"C:\Windows\Fonts\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]),
):
    for p in paths:
        if Path(p).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, p))
                if name == "Inter":
                    FONT_REG = "Inter"
                elif name == "Inter-Bold":
                    FONT_BOLD = "Inter-Bold"
                elif name == "Mono":
                    FONT_MONO = "Mono"
                break
            except Exception:
                pass


# ============== drawing helpers ==============

def fill_bg(c: canvas.Canvas) -> None:
    c.setFillColor(BG)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    # Soft purple halo top-left
    halo(c, 0.20 * W, 0.95 * H, 0.7 * W, ACCENT, 0.18)
    # Soft blue halo bottom-right
    halo(c, 1.05 * W, -0.05 * H, 0.55 * W, ACCENT_2, 0.10)


def halo(c: canvas.Canvas, cx: float, cy: float, r: float, color: HexColor, alpha: float) -> None:
    """Draw a circular gradient halo by stacking translucent circles."""
    steps = 16
    for i in range(steps, 0, -1):
        a = alpha * (i / steps) ** 2.5
        c.setFillColor(Color(color.red, color.green, color.blue, alpha=a))
        rr = r * (i / steps)
        c.circle(cx, cy, rr, stroke=0, fill=1)


def gradient_bar(c: canvas.Canvas, x: float, y: float, w: float, h: float,
                  c1: HexColor, c2: HexColor, vertical: bool = False) -> None:
    """Approximate a 2-color linear gradient with vertical/horizontal stripes."""
    steps = 64
    if vertical:
        for i in range(steps):
            t = i / (steps - 1)
            c.setFillColor(_lerp(c1, c2, t))
            c.rect(x, y + (h / steps) * i, w, h / steps + 0.5, stroke=0, fill=1)
    else:
        for i in range(steps):
            t = i / (steps - 1)
            c.setFillColor(_lerp(c1, c2, t))
            c.rect(x + (w / steps) * i, y, w / steps + 0.5, h, stroke=0, fill=1)


def _lerp(a: HexColor, b: HexColor, t: float) -> Color:
    return Color(
        a.red + (b.red - a.red) * t,
        a.green + (b.green - a.green) * t,
        a.blue + (b.blue - a.blue) * t,
    )


def card(c: canvas.Canvas, x: float, y: float, w: float, h: float,
          fill: HexColor = BG_2, border: HexColor = BORDER, radius: float = 12) -> None:
    c.setFillColor(fill)
    c.setStrokeColor(border)
    c.setLineWidth(0.7)
    c.roundRect(x, y, w, h, radius, stroke=1, fill=1)


def text(c: canvas.Canvas, x: float, y: float, txt: str, *, size: float = 14,
          color: HexColor = FG, font: str = None, align: str = "left") -> None:
    c.setFillColor(color)
    c.setFont(font or FONT_REG, size)
    if align == "center":
        c.drawCentredString(x, y, txt)
    elif align == "right":
        c.drawRightString(x, y, txt)
    else:
        c.drawString(x, y, txt)


def wrap_text(c: canvas.Canvas, x: float, y: float, txt: str, *, size: float = 14,
               color: HexColor = FG, font: str = None, max_width: float = 500,
               leading: float = 1.4) -> float:
    """Word-wrap a paragraph at max_width; return final y position."""
    c.setFillColor(color)
    c.setFont(font or FONT_REG, size)
    words = txt.split()
    line = ""
    line_h = size * leading
    for w in words:
        candidate = line + (" " if line else "") + w
        if c.stringWidth(candidate, font or FONT_REG, size) > max_width:
            c.drawString(x, y, line)
            y -= line_h
            line = w
        else:
            line = candidate
    if line:
        c.drawString(x, y, line)
        y -= line_h
    return y


def page_number(c: canvas.Canvas, n: int, total: int, show_url: bool = True) -> None:
    c.setFillColor(MUTED)
    c.setFont(FONT_MONO, 9)
    c.drawString(0.45 * inch, 0.3 * inch, f"Cascade · {n:02d} / {total:02d}")
    if show_url:
        c.drawRightString(W - 0.45 * inch, 0.3 * inch, "github.com/RC6HEX/cascade")


def cascade_logo(c: canvas.Canvas, cx: float, cy: float, size: float = 28) -> None:
    """Draw the 4-quadrant Cascade logo (gradient squares)."""
    s = size / 2.4
    gap = size * 0.07
    # top-left → bottom-right corners with gradient colors
    quads = [
        (-s - gap / 2, gap / 2, ACCENT, 1.0),
        (gap / 2, gap / 2, ACCENT_2, 0.7),
        (-s - gap / 2, -s - gap / 2, ACCENT_3, 0.55),
        (gap / 2, -s - gap / 2, WARN, 0.4),
    ]
    for dx, dy, col, alpha in quads:
        c.setFillColor(Color(col.red, col.green, col.blue, alpha=alpha))
        c.roundRect(cx + dx, cy + dy, s, s, 1.2, stroke=0, fill=1)


def page_header(c: canvas.Canvas, title: str, subtitle: str | None = None) -> None:
    """Top brand strip + slide title."""
    cascade_logo(c, 0.55 * inch, H - 0.55 * inch, size=22)
    text(c, 0.85 * inch, H - 0.55 * inch + 4, "Cascade", size=12, color=FG_2, font=FONT_BOLD)
    text(c, 0.85 * inch, H - 0.55 * inch - 6, "автономный генератор приложений",
         size=8, color=MUTED, font=FONT_MONO)

    # Title
    text(c, 0.65 * inch, H - 1.55 * inch, title, size=30, color=FG, font=FONT_BOLD)
    if subtitle:
        text(c, 0.65 * inch, H - 1.95 * inch, subtitle, size=14, color=MUTED)

    # Accent bar under header (3px tall, gradient)
    gradient_bar(c, 0.65 * inch, H - 0.85 * inch, 1.6 * inch, 0.04 * inch, ACCENT, ACCENT_2)


# ============== slide builders ==============

def slide_title(c: canvas.Canvas) -> None:
    """Slide 1 — title."""
    fill_bg(c)
    # Bigger logo center-top
    cascade_logo(c, W / 2, H / 2 + 1.4 * inch, size=80)

    # CASCADE big title
    c.setFont(FONT_BOLD, 96)
    c.setFillColor(FG)
    c.drawCentredString(W / 2, H / 2 - 0.0 * inch, "Cascade")

    # Tagline
    c.setFont(FONT_REG, 22)
    c.setFillColor(FG_2)
    c.drawCentredString(W / 2, H / 2 - 0.7 * inch, "автономная команда разработки ПО")
    c.setFont(FONT_MONO, 13)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, H / 2 - 1.1 * inch,
                        "БТ → UC → НФТ → ФТ → код → тесты → README")

    # Metric badges row — proves it works
    badges = [
        ("100%", "БТ → ФТ", ACCENT),
        ("12", "файлов", ACCENT_2),
        ("$0.02", "/прогон", ACCENT_3),
        ("3.4 мин", "end-to-end", WARN),
    ]
    bw = 1.6 * inch
    bh = 0.7 * inch
    total_w = len(badges) * bw + (len(badges) - 1) * 0.2 * inch
    bx_start = (W - total_w) / 2
    by = H / 2 - 2.4 * inch
    for i, (val, lbl, col) in enumerate(badges):
        x = bx_start + i * (bw + 0.2 * inch)
        c.setFillColor(BG_2)
        c.setStrokeColor(col)
        c.setLineWidth(1.2)
        c.roundRect(x, by, bw, bh, 8, stroke=1, fill=1)
        text(c, x + bw / 2, by + 0.42 * inch, val,
             size=18, color=col, font=FONT_BOLD, align="center")
        text(c, x + bw / 2, by + 0.15 * inch, lbl,
             size=10, color=FG_2, align="center")
    c.setLineWidth(1.0)

    # Bottom links bar
    c.setFont(FONT_MONO, 13)
    c.setFillColor(ACCENT)
    c.drawCentredString(W / 2, 1.0 * inch, "github.com/RC6HEX/cascade")
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, 0.65 * inch, "rc6hex.github.io/cascade  ·  live demo")


def slide_problem(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Разработка ПО — это не только код",
                 "почему один промпт ≠ полноценный проект")

    bullets = [
        ("01", "LLM пишут код", "но не делают требования, архитектуру, тесты"),
        ("02", "Трассировка теряется", "почему именно эта функция? откуда взялась?"),
        ("03", "Один промпт", "≠ полноценный проект с документацией"),
    ]
    y = H - 3.0 * inch
    for num, title_, desc in bullets:
        card(c, 0.65 * inch, y - 0.7 * inch, W - 1.3 * inch, 0.95 * inch, fill=BG_2)
        text(c, 1.0 * inch, y - 0.25 * inch, num, size=28, color=ACCENT, font=FONT_BOLD)
        text(c, 2.0 * inch, y - 0.2 * inch, title_, size=18, color=FG, font=FONT_BOLD)
        text(c, 2.0 * inch, y - 0.5 * inch, desc, size=13, color=FG_2)
        y -= 1.3 * inch


def slide_idea(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Приложение, которое создаёт другие приложения",
                 "вход → каскад артефактов → готовый проект")

    # Two columns: input / output
    col_w = (W - 1.3 * inch - 0.6 * inch) / 2

    # Input
    card(c, 0.65 * inch, H - 5.5 * inch, col_w, 3.0 * inch)
    text(c, 0.85 * inch, H - 2.7 * inch, "ВХОД", size=10, color=MUTED, font=FONT_BOLD)
    text(c, 0.85 * inch, H - 3.0 * inch, "Markdown-документы", size=18, color=FG, font=FONT_BOLD)
    items_in = [
        ("БТ", "бизнес-требования", ACCENT),
        ("БП", "бизнес-процесс", ACCENT_2),
        ("Features", "характеристики (опционально)", ACCENT_3),
    ]
    yy = H - 3.5 * inch
    for tag, desc, col in items_in:
        c.setFillColor(col)
        c.roundRect(0.85 * inch, yy - 0.05 * inch, 0.85 * inch, 0.3 * inch, 4, stroke=0, fill=1)
        c.setFillColor(BG)
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(0.85 * inch + 0.425 * inch, yy + 0.04 * inch, tag)
        text(c, 1.85 * inch, yy + 0.05 * inch, desc, size=13, color=FG_2)
        yy -= 0.5 * inch

    # Arrow between
    arrow_x = 0.65 * inch + col_w + 0.1 * inch
    text(c, arrow_x + 0.2 * inch, H - 4.0 * inch, "→", size=40, color=ACCENT, font=FONT_BOLD)

    # Output
    out_x = 0.65 * inch + col_w + 0.6 * inch
    card(c, out_x, H - 5.5 * inch, col_w, 3.0 * inch)
    text(c, out_x + 0.2 * inch, H - 2.7 * inch, "ВЫХОД", size=10, color=MUTED, font=FONT_BOLD)
    text(c, out_x + 0.2 * inch, H - 3.0 * inch, "Готовый проект", size=18, color=FG, font=FONT_BOLD)
    items_out = [
        ("src/", "исходный код приложения"),
        ("docs/", "use-cases, НФТ, ФТ"),
        ("tests/", "Vitest unit-тесты"),
        ("README.md", "инструкция к запуску"),
    ]
    yy = H - 3.5 * inch
    for path, desc in items_out:
        text(c, out_x + 0.2 * inch, yy + 0.05 * inch, path, size=13, color=ACCENT, font=FONT_MONO)
        text(c, out_x + 1.5 * inch, yy + 0.05 * inch, desc, size=12, color=FG_2)
        yy -= 0.4 * inch


def slide_cascade(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Каскад артефактов",
                 "каждый уровень ссылается на предыдущий")

    # Horizontal pipeline
    steps = [
        ("БТ + БП", "вход", BG_3),
        ("Use Cases", "сценарии", ACCENT_2),
        ("НФТ", "нефункц. требования", ACCENT),
        ("ФТ", "функц. требования", ACCENT_3),
        ("Код", "src/", WARN),
        ("Тесты", "Vitest", DANGER),
    ]
    n = len(steps)
    spacing = (W - 1.3 * inch) / n
    bx = 0.65 * inch
    by = H - 4.5 * inch
    for i, (title_, sub, col) in enumerate(steps):
        x = bx + spacing * i
        card(c, x + 0.1 * inch, by, spacing - 0.2 * inch, 1.4 * inch, fill=BG_2,
              border=col)
        # Top accent line
        c.setFillColor(col)
        c.rect(x + 0.1 * inch, by + 1.36 * inch, spacing - 0.2 * inch, 0.04 * inch, stroke=0, fill=1)
        text(c, x + spacing / 2, by + 0.85 * inch, title_, size=15, color=FG,
              font=FONT_BOLD, align="center")
        text(c, x + spacing / 2, by + 0.55 * inch, sub, size=10, color=MUTED, align="center")
        # Arrow to next
        if i < n - 1:
            c.setFillColor(ACCENT)
            c.setFont(FONT_BOLD, 18)
            c.drawCentredString(x + spacing - 0.05 * inch, by + 0.65 * inch, "›")

    # Trace example
    yy = H - 5.6 * inch
    text(c, 0.65 * inch, yy, "Пример трассировки одного требования:",
         size=11, color=MUTED, font=FONT_BOLD)
    yy -= 0.4 * inch

    chain = [("БТ-04", ACCENT_2), ("UC-01 alt", ACCENT), ("ФТ-05", ACCENT_3),
             ("@implements ФТ-05", WARN), ("calculator.test.js", DANGER)]
    xx = 0.65 * inch
    for tag, col in chain:
        w_t = c.stringWidth(tag, FONT_MONO, 11) + 16
        c.setFillColor(col)
        c.roundRect(xx, yy - 5, w_t, 22, 3, stroke=0, fill=1)
        c.setFillColor(BG)
        c.setFont(FONT_MONO, 11)
        c.drawString(xx + 8, yy + 2, tag)
        xx += w_t + 6
        if tag != chain[-1][0]:
            c.setFillColor(MUTED)
            c.setFont(FONT_BOLD, 14)
            c.drawString(xx + 2, yy, "›")
            xx += 22


def slide_architecture(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Архитектура", "три слоя, чёткие границы")

    # Three layer cards
    layers = [
        ("Web UI", "FastAPI · SSE · vanilla JS", [
            "POST /api/jobs",
            "GET .../stream (SSE)",
            "GET .../app/{path}",
            "GET .../traceability",
        ], ACCENT),
        ("pipeline.py", "6 шагов с self-check", [
            "use_cases · nfr · fr",
            "code (streaming)",
            "tests · readme",
            "self-check loops",
        ], ACCENT_2),
        ("llm.py", "OpenRouter / Gemini", [
            "retry с backoff (429, 5xx)",
            "streaming через httpx",
            "thread-safe Usage",
            "12 моделей",
        ], ACCENT_3),
    ]
    col_w = (W - 1.3 * inch - 0.6 * inch) / 3
    by = H - 5.7 * inch
    bh = 3.5 * inch
    for i, (title_, sub, items, col) in enumerate(layers):
        x = 0.65 * inch + (col_w + 0.3 * inch) * i
        card(c, x, by, col_w, bh, border=col)
        # Top color bar
        c.setFillColor(col)
        c.rect(x, by + bh - 0.05 * inch, col_w, 0.05 * inch, stroke=0, fill=1)
        text(c, x + 0.25 * inch, by + bh - 0.5 * inch, title_, size=18, color=FG, font=FONT_BOLD)
        text(c, x + 0.25 * inch, by + bh - 0.8 * inch, sub, size=11, color=MUTED, font=FONT_MONO)
        yy = by + bh - 1.3 * inch
        for it in items:
            c.setFillColor(col)
            c.circle(x + 0.32 * inch, yy + 0.08 * inch, 0.05 * inch, stroke=0, fill=1)
            text(c, x + 0.5 * inch, yy + 0.04 * inch, it, size=11, color=FG_2)
            yy -= 0.32 * inch


def slide_stack(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Стек", "vanilla > магия")

    items = [
        ("PY", "Python 3.11+", "httpx + FastAPI + Uvicorn"),
        ("LLM", "LLM провайдеры", "OpenRouter (12 моделей) или Gemini API"),
        ("APP", "Сгенерированные приложения", "vanilla HTML + JS + CSS, без сборки"),
        ("QA", "Тесты сгенерированных", "Vitest + happy-dom"),
        ("UI", "Web интерфейс", "FastAPI + SSE + vanilla JS, без React/Vue"),
        ("NO", "Без LangChain / CrewAI", "контроль над промптами > магия агентов"),
    ]
    col_w = (W - 1.3 * inch - 0.4 * inch) / 2
    yy = H - 3.0 * inch
    for i, (icon, title_, desc) in enumerate(items):
        col = i % 2
        row = i // 2
        x = 0.65 * inch + (col_w + 0.4 * inch) * col
        y = yy - row * 1.4 * inch
        card(c, x, y - 1.05 * inch, col_w, 1.05 * inch)
        # Icon circle
        circle_color = ACCENT if i % 3 == 0 else (ACCENT_2 if i % 3 == 1 else ACCENT_3)
        c.setFillColor(circle_color)
        c.circle(x + 0.5 * inch, y - 0.55 * inch, 0.27 * inch, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(x + 0.5 * inch, y - 0.6 * inch, icon)
        text(c, x + 1.05 * inch, y - 0.4 * inch, title_, size=15, color=FG, font=FONT_BOLD)
        text(c, x + 1.05 * inch, y - 0.7 * inch, desc, size=11, color=FG_2)


def slide_models(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "12 моделей через OpenRouter",
                 "переключаются live в Settings — без рестарта")

    models = [
        ("DeepSeek V3", "0.27 / 1.10", "64K", "дефолт smart", ACCENT),
        ("Qwen 2.5 72B", "0.13 / 0.40", "32K", "дефолт fast", ACCENT_2),
        ("DeepSeek R1", "0.55 / 2.19", "64K", "reasoning", ACCENT_3),
        ("Llama 3.3 70B", "0.13 / 0.40", "128K", "универсальная", WARN),
        ("MiniMax 01", "0.20 / 1.10", "1M", "длинный контекст", ACCENT),
        ("Gemini 2.5 Pro", "1.25 / 10.00", "1M", "максимум качества", ACCENT_2),
        ("Gemini 2.5 Flash", "0.30 / 2.50", "1M", "баланс", ACCENT_3),
        ("Claude 3.5 Haiku", "0.80 / 4.00", "200K", "стабильно", WARN),
        ("Qwen 2.5 Coder 32B", "0.07 / 0.16", "32K", "код", ACCENT),
        ("Mistral Small 3.2", "0.10 / 0.30", "96K", "быстрая", ACCENT_2),
        ("Qwen 2.5 7B", "0.04 / 0.10", "32K", "стресс-тест", ACCENT_3),
        ("Llama 3.2 3B", "0.02 / 0.04", "128K", "отладка", WARN),
    ]
    # Header
    yy = H - 2.8 * inch
    cols_x = [0.7 * inch, 4.3 * inch, 5.6 * inch, 6.6 * inch]
    headers_t = ("Модель", "$ in / out (1M)", "контекст", "применение")
    for x, ht in zip(cols_x, headers_t):
        text(c, x, yy, ht, size=10, color=MUTED, font=FONT_BOLD)
    c.setStrokeColor(BORDER)
    c.line(0.65 * inch, yy - 0.1 * inch, W - 0.65 * inch, yy - 0.1 * inch)

    yy -= 0.4 * inch
    for name, price, ctx, note, col in models:
        # Color tag
        c.setFillColor(col)
        c.circle(0.55 * inch, yy + 0.05 * inch, 0.05 * inch, stroke=0, fill=1)
        text(c, 0.7 * inch, yy, name, size=11, color=FG, font=FONT_BOLD)
        # Higher contrast: white-ish + accent green only on the slash
        text(c, 4.3 * inch, yy, "$" + price, size=11, color=FG, font=FONT_MONO)
        text(c, 5.6 * inch, yy, ctx, size=11, color=FG_2, font=FONT_MONO)
        text(c, 6.6 * inch, yy, note, size=11, color=FG_2)
        yy -= 0.32 * inch


def slide_personas(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Каждому шагу — свой эксперт",
                 "persona-driven prompts: модель пишет ФТ как продакт, код как сеньор")

    personas = [
        ("1", "use_cases", "Senior Business Analyst, 15 лет", "форматные UC с источниками БТ"),
        ("2", "nfr", "Solution Architect", "измеримые критерии с числами"),
        ("3", "fr", "техлид + системный аналитик", "обязательная трассировка БТ → ФТ"),
        ("4", "code", "Senior Frontend Engineer L7", "@implements ФТ + кодекс качества"),
        ("5", "tests", "QA-инженер с диким взглядом", "ловит регрессии до релиза"),
        ("6", "readme", "технический писатель", "копипастные команды, без воды"),
    ]
    yy = H - 2.9 * inch
    for icon, step, persona, role in personas:
        card(c, 0.65 * inch, yy - 0.55 * inch, W - 1.3 * inch, 0.6 * inch)
        # Icon
        c.setFillColor(ACCENT)
        c.circle(0.95 * inch, yy - 0.27 * inch, 0.18 * inch, stroke=0, fill=1)
        c.setFillColor(white)
        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(0.95 * inch, yy - 0.32 * inch, icon)
        # Step name (mono, accent)
        text(c, 1.35 * inch, yy - 0.27 * inch, step, size=13, color=ACCENT, font=FONT_MONO)
        # Persona
        text(c, 2.6 * inch, yy - 0.27 * inch, persona, size=14, color=FG, font=FONT_BOLD)
        # Role
        text(c, 6.7 * inch, yy - 0.27 * inch, "-> " + role, size=12, color=FG_2)
        yy -= 0.7 * inch


def slide_selfcheck(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Self-check loops",
                 "главное усиление по ТЗ — резко поднимает качество")

    # Big stat left
    card(c, 0.65 * inch, 1.3 * inch, 4.5 * inch, 4.0 * inch, border=ACCENT_3)
    c.setFillColor(ACCENT_3)
    c.rect(0.65 * inch, 5.3 * inch - 0.05 * inch, 4.5 * inch, 0.05 * inch, stroke=0, fill=1)
    text(c, 2.9 * inch, 4.5 * inch, "100%", size=72, color=ACCENT_3, font=FONT_BOLD,
         align="center")
    text(c, 2.9 * inch, 3.6 * inch, "обязательных БТ", size=14, color=FG_2, align="center")
    text(c, 2.9 * inch, 3.3 * inch, "покрыто ФТ", size=14, color=FG_2, align="center")
    text(c, 2.9 * inch, 2.4 * inch, "после ретраев", size=11, color=MUTED, align="center")
    text(c, 2.9 * inch, 2.05 * inch, "(в среднем — 1 ретрай на FR-step)", size=10,
         color=MUTED, align="center")

    # Steps right + concrete real-run example
    rx = 5.5 * inch
    text(c, rx, 5.0 * inch, "Как работает", size=12, color=MUTED, font=FONT_BOLD)
    steps = [
        ("1", "Шаг сгенерирован", FG),
        ("2", "Validator парсит ID:\nБТ → ФТ → @implements", FG_2),
        ("3", "Не покрыто? — feedback модели", FG_2),
        ("4", "Шаг переделывается, до 2 ретраев", ACCENT_3),
    ]
    yy = 4.5 * inch
    for num, txt, col in steps:
        c.setFillColor(ACCENT)
        c.circle(rx + 0.2 * inch, yy + 0.05 * inch, 0.18 * inch, stroke=0, fill=1)
        text(c, rx + 0.2 * inch, yy, num, size=14, color=white, font=FONT_BOLD,
             align="center")
        for li, ln in enumerate(txt.split("\n")):
            text(c, rx + 0.55 * inch, yy + 0.05 * inch - li * 0.25 * inch,
                 ln, size=12, color=col)
        yy -= 0.6 * inch

    # Concrete example from real run
    ex_y = 1.5 * inch
    card(c, rx, ex_y, W - rx - 0.65 * inch, 1.0 * inch, fill=BG_2, border=WARN)
    c.setFillColor(WARN)
    c.rect(rx, ex_y + 1.0 * inch - 0.04 * inch, W - rx - 0.65 * inch, 0.04 * inch,
           stroke=0, fill=1)
    text(c, rx + 0.2 * inch, ex_y + 0.7 * inch, "ПРИМЕР ИЗ РЕАЛЬНОГО ПРОГОНА",
         size=9, color=WARN, font=FONT_BOLD)
    text(c, rx + 0.2 * inch, ex_y + 0.4 * inch,
         "FR-step: «missing БТ-05 в источниках»", size=11, color=FG, font=FONT_MONO)
    text(c, rx + 0.2 * inch, ex_y + 0.15 * inch,
         "→ retry 1 → ✓ ФТ-04 теперь ссылается на БТ-05",
         size=11, color=ACCENT_3, font=FONT_MONO)


def slide_streaming(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Streaming partial output",
                 "код пишется в UI на лету — не ждёшь 2 минуты")

    # Mock terminal/code-streaming visual
    card(c, 0.65 * inch, 1.5 * inch, W - 1.3 * inch, 4.0 * inch, fill=BG, border=ACCENT)
    # Top status bar
    c.setFillColor(BG_2)
    c.rect(0.65 * inch, 5.0 * inch, W - 1.3 * inch, 0.5 * inch, stroke=0, fill=1)
    text(c, 0.85 * inch, 5.18 * inch, "// live streaming", size=11, color=ACCENT, font=FONT_BOLD)
    text(c, W - 0.85 * inch, 5.18 * inch, "src/calculator.js · 1.2 KB", size=10,
         color=MUTED, align="right", font=FONT_MONO)

    snippet = [
        "/**",
        " * @implements ФТ-01",
        " * @implements ФТ-04",
        " */",
        "export class Calculator {",
        "    constructor() {",
        "        this.currentInput = '0';",
        "        this.prevInput = null;",
        "        this.history = [];",
        "    }",
        "    handleNumberInput(n) {",
        "        if (this.resetNextInput) {█",
    ]
    yy = 4.7 * inch
    for line in snippet:
        col = ACCENT if "@implements" in line else (ACCENT_2 if "ФТ" in line else FG_2)
        text(c, 0.85 * inch, yy, line, size=12, color=col, font=FONT_MONO)
        yy -= 0.25 * inch


def slide_parallel(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Параллелизация шагов",
                 "use_cases + nfr — независимые → запускаются одновременно")

    # Before/after comparison — top edge ≤ CONTENT_TOP (= 5.15")
    col_w = (W - 1.3 * inch - 0.4 * inch) / 2
    card_top = 5.0 * inch  # fits under subtitle
    card_bottom = 1.0 * inch
    card_height = card_top - card_bottom

    # Before
    card(c, 0.65 * inch, card_bottom, col_w, card_height, fill=BG_2, border=BORDER)
    text(c, 0.65 * inch + col_w / 2, card_top - 0.4 * inch, "ДО",
         size=10, color=MUTED, font=FONT_BOLD, align="center")
    text(c, 0.65 * inch + col_w / 2, card_top - 0.7 * inch, "последовательно",
         size=14, color=FG, font=FONT_BOLD, align="center")
    yy = card_top - 1.3 * inch
    for label, dur in [("use_cases", "20s"), ("nfr", "20s")]:
        c.setFillColor(MUTED)
        c.rect(0.85 * inch, yy, 4.5 * inch, 0.35 * inch, stroke=0, fill=1)
        text(c, 0.95 * inch, yy + 0.1 * inch, label, size=11, color=BG, font=FONT_MONO)
        text(c, 5.3 * inch, yy + 0.1 * inch, dur, size=11, color=BG, font=FONT_MONO,
             align="right")
        yy -= 0.55 * inch
    text(c, 0.65 * inch + col_w / 2, card_bottom + 0.7 * inch, "Σ ≈ 40 секунд",
         size=22, color=DANGER, font=FONT_BOLD, align="center")

    # After
    rx = 0.65 * inch + col_w + 0.4 * inch
    card(c, rx, card_bottom, col_w, card_height, fill=BG_2, border=ACCENT_3)
    text(c, rx + col_w / 2, card_top - 0.4 * inch, "ПОСЛЕ",
         size=10, color=ACCENT_3, font=FONT_BOLD, align="center")
    text(c, rx + col_w / 2, card_top - 0.7 * inch, "ThreadPoolExecutor(2)",
         size=14, color=FG, font=FONT_BOLD, align="center")

    yy = card_top - 1.3 * inch
    for label in ["use_cases · 20s", "nfr · 20s"]:
        c.setFillColor(ACCENT_3)
        c.rect(rx + 0.2 * inch, yy, 4.5 * inch, 0.35 * inch, stroke=0, fill=1)
        text(c, rx + 0.3 * inch, yy + 0.1 * inch, label, size=11, color=BG, font=FONT_MONO)
        yy -= 0.45 * inch
    text(c, rx + col_w / 2, card_bottom + 1.0 * inch, "Σ ≈ 20 секунд",
         size=22, color=ACCENT_3, font=FONT_BOLD, align="center")
    text(c, rx + col_w / 2, card_bottom + 0.6 * inch, "−50% времени на этих шагах",
         size=11, color=FG_2, align="center")


def slide_refine(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Refinement mode",
                 "короткий комментарий → точечные правки (по ТЗ)")

    # Example flow — fits under subtitle
    ex_top = 5.0 * inch
    ex_h = 1.5 * inch
    card(c, 0.65 * inch, ex_top - ex_h, W - 1.3 * inch, ex_h, fill=BG_2)
    text(c, 0.85 * inch, ex_top - 0.35 * inch, "ПРИМЕР", size=10, color=MUTED, font=FONT_BOLD)
    text(c, 0.85 * inch, ex_top - 0.65 * inch, "«поменяй цветовую схему на синюю»",
         size=18, color=FG, font=FONT_BOLD)
    text(c, 0.85 * inch, ex_top - 1.0 * inch, "↓ ", size=14, color=ACCENT, font=FONT_BOLD)
    text(c, 1.05 * inch, ex_top - 1.25 * inch, "изменён только src/styles.css",
         size=14, color=ACCENT_3, font=FONT_MONO)

    # Stats row
    stats = [
        ("40s", "длительность"),
        ("1", "LLM call"),
        ("1", "файл изменён"),
        ("4", "файла нетронуты"),
    ]
    sw = (W - 1.3 * inch - 0.6 * inch) / 4
    yy = 1.3 * inch
    for i, (n, lbl) in enumerate(stats):
        x = 0.65 * inch + (sw + 0.2 * inch) * i
        card(c, x, yy, sw, 1.9 * inch, fill=BG_2, border=ACCENT)
        text(c, x + sw / 2, yy + 1.3 * inch, n, size=42, color=ACCENT, font=FONT_BOLD,
             align="center")
        text(c, x + sw / 2, yy + 0.6 * inch, lbl, size=11, color=FG_2, align="center")


def slide_preview(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Live app preview",
                 "сгенерированное приложение запускается в iframe прямо в UI -> 7+3=10")

    # Mock browser frame with a calculator
    bx = 0.65 * inch
    by = 1.5 * inch
    bw = W - 1.3 * inch
    bh = 4.0 * inch
    card(c, bx, by, bw, bh, fill=white, border=BORDER, radius=8)

    # Top bar (like browser)
    c.setFillColor(BG_3)
    c.rect(bx, by + bh - 0.4 * inch, bw, 0.4 * inch, stroke=0, fill=1)
    for i, col in enumerate([DANGER, WARN, ACCENT_3]):
        c.setFillColor(col)
        c.circle(bx + 0.2 * inch + i * 0.3 * inch, by + bh - 0.2 * inch, 0.07 * inch,
                 stroke=0, fill=1)
    text(c, bx + bw / 2, by + bh - 0.27 * inch, "QuickCalc · localhost:8000",
         size=10, color=MUTED, align="center", font=FONT_MONO)

    # Calculator display — placed above buttons (top row top edge at 3.75")
    cx = bx + bw / 2
    text(c, cx, by + 2.95 * inch, "10", size=64, color=BG, font=FONT_BOLD, align="center")
    text(c, cx, by + 2.5 * inch, "7 + 3 =", size=14, color=MUTED, align="center",
         font=FONT_MONO)

    # Calculator buttons — centered horizontally inside the window
    btn_labels = [["7", "8", "9", "÷"], ["4", "5", "6", "×"], ["1", "2", "3", "−"], ["0", ".", "=", "+"]]
    bsize = 0.55 * inch
    gap = 0.1 * inch
    grid_w = 4 * bsize + 3 * gap  # 2.5"
    bxx = bx + (bw - grid_w) / 2
    byy = by + 1.7 * inch
    for r, row in enumerate(btn_labels):
        for col_i, lbl in enumerate(row):
            x = bxx + col_i * (bsize + gap)
            y = byy - r * (bsize + gap)
            is_op = lbl in ("÷", "×", "−", "+", "=")
            c.setFillColor(ACCENT if is_op else BG_3)
            c.roundRect(x, y, bsize, bsize, 6, stroke=0, fill=1)
            c.setFillColor(white)
            c.setFont(FONT_BOLD, 16)
            c.drawCentredString(x + bsize / 2, y + bsize / 2 - 5, lbl)


def slide_traceability(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Traceability matrix",
                 "БТ -> UC -> ФТ -> @implements в одной картинке")

    # 5 stat cards — REAL data from job 7709e2dcca16
    stats = [
        ("5", "БТ всего", FG),
        ("4", "обязательных", ACCENT),
        ("4", "юз-кейсов", ACCENT_2),
        ("7", "ФТ", ACCENT_3),
        ("100%", "ФТ → @implements", ACCENT_3),
    ]
    sw = (W - 1.3 * inch - 0.8 * inch) / 5
    sh = 1.4 * inch
    yy = 3.7 * inch  # top = 5.1 ≤ 5.15
    for i, (n, lbl, col) in enumerate(stats):
        x = 0.65 * inch + (sw + 0.2 * inch) * i
        card(c, x, yy, sw, sh, border=col)
        text(c, x + sw / 2, yy + 0.95 * inch, n, size=34, color=col, font=FONT_BOLD,
             align="center")
        text(c, x + sw / 2, yy + 0.35 * inch, lbl, size=10, color=FG_2, align="center",
             font=FONT_BOLD)

    # Matrix preview — REAL traceability from output of latest run
    rx = 0.65 * inch
    rw = W - 1.3 * inch
    text(c, rx, 3.3 * inch, "матрица в UI · реальные данные из последнего прогона:",
         size=11, color=MUTED, font=FONT_BOLD)

    rows = [
        ("БТ-01", "обяз.", "UC-01", "ФТ-01"),
        ("БТ-02", "опц.", "UC-02", "ФТ-05, ФТ-06"),
        ("БТ-03", "обяз.", "UC-02", "ФТ-03, ФТ-04"),
        ("БТ-04", "обяз.", "UC-01", "ФТ-02"),
        ("БТ-05", "обяз.", "UC-03", "ФТ-07"),
    ]
    rh = 0.32 * inch
    table_top = 2.95 * inch
    yy_h = table_top  # column header row baseline
    text(c, rx + 0.1 * inch, yy_h, "БТ", size=10, color=MUTED, font=FONT_BOLD)
    text(c, rx + 1.2 * inch, yy_h, "обязательность", size=10, color=MUTED, font=FONT_BOLD)
    text(c, rx + 3.5 * inch, yy_h, "UC", size=10, color=MUTED, font=FONT_BOLD)
    text(c, rx + 5.5 * inch, yy_h, "ФТ", size=10, color=MUTED, font=FONT_BOLD)
    # Separator line below header
    c.setStrokeColor(BORDER)
    c.line(rx, yy_h - 0.12 * inch, rx + rw, yy_h - 0.12 * inch)

    yy_first_row = yy_h - 0.45 * inch
    for i, (bt, req, uc, frs) in enumerate(rows):
        cy = yy_first_row - i * rh
        # Subtle stripe for readability
        if i % 2 == 0:
            c.setFillColor(Color(BG_2.red, BG_2.green, BG_2.blue, alpha=0.5))
            c.rect(rx, cy - 0.07 * inch, rw, rh, stroke=0, fill=1)
        text(c, rx + 0.1 * inch, cy + 0.05 * inch, bt, size=11, color=ACCENT_2,
             font=FONT_MONO)
        text(c, rx + 1.2 * inch, cy + 0.05 * inch, req, size=11, color=FG_2)
        text(c, rx + 3.5 * inch, cy + 0.05 * inch, uc, size=11, color=ACCENT,
             font=FONT_MONO)
        text(c, rx + 5.5 * inch, cy + 0.05 * inch, frs, size=11, color=ACCENT_3,
             font=FONT_MONO)


def slide_perstep(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Per-step model picker",
                 "модель на каждый из 6 шагов отдельно")

    # 6 dropdowns visualization
    steps = [("use_cases", "Llama 3.2 3B (debug)"), ("nfr", "Qwen 2.5 72B"),
             ("fr", "DeepSeek V3"), ("code", "Claude 3.5 Haiku"),
             ("tests", "Qwen 2.5 7B"), ("readme", "Mistral Small")]
    cw = (W - 1.3 * inch - 0.4 * inch) / 2
    by = H - 6.5 * inch
    bh = 0.9 * inch
    yy = H - 3.0 * inch
    for i, (step, model) in enumerate(steps):
        col = i % 2
        row = i // 2
        x = 0.65 * inch + (cw + 0.4 * inch) * col
        y = yy - row * (bh + 0.3 * inch)
        card(c, x, y - bh, cw, bh)
        text(c, x + 0.25 * inch, y - 0.3 * inch, step, size=11, color=MUTED, font=FONT_MONO)
        text(c, x + 0.25 * inch, y - 0.65 * inch, model, size=14, color=FG, font=FONT_BOLD)
        # Down arrow icon
        text(c, x + cw - 0.4 * inch, y - 0.5 * inch, "▼", size=12, color=ACCENT)


def slide_history_cost(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Job history + cost estimator",
                 "генерации переживают рестарт сервера")

    cw = (W - 1.3 * inch - 0.5 * inch) / 2

    # History card
    card(c, 0.65 * inch, 1.5 * inch, cw, 4.4 * inch, border=ACCENT)
    c.setFillColor(ACCENT)
    c.rect(0.65 * inch, 5.85 * inch, cw, 0.05 * inch, stroke=0, fill=1)
    text(c, 0.85 * inch, 5.5 * inch, "ИСТОРИЯ ЗАПУСКОВ", size=10, color=MUTED, font=FONT_BOLD)
    text(c, 0.85 * inch, 5.15 * inch, "Job persistence", size=18, color=FG, font=FONT_BOLD)
    items = [
        "_job_meta.json на диск после каждого пайплайна",
        "_scan_disk_jobs() при startup восстанавливает всё",
        "GET /api/jobs — sorted by mtime",
        "Sticky panel в UI: status / task / files",
        "Replay сохранённых SSE-событий",
    ]
    yy = 4.6 * inch
    for it in items:
        c.setFillColor(ACCENT)
        c.circle(0.85 * inch, yy + 0.07 * inch, 0.04 * inch, stroke=0, fill=1)
        text(c, 1.0 * inch, yy + 0.04 * inch, it, size=11, color=FG_2)
        yy -= 0.36 * inch

    # Cost card
    rx = 0.65 * inch + cw + 0.5 * inch
    card(c, rx, 1.5 * inch, cw, 4.4 * inch, border=ACCENT_3)
    c.setFillColor(ACCENT_3)
    c.rect(rx, 5.85 * inch, cw, 0.05 * inch, stroke=0, fill=1)
    text(c, rx + 0.2 * inch, 5.5 * inch, "СТОИМОСТЬ", size=10, color=MUTED, font=FONT_BOLD)
    text(c, rx + 0.2 * inch, 5.15 * inch, "Live cost estimator", size=18, color=FG,
         font=FONT_BOLD)
    text(c, rx + 0.2 * inch, 4.75 * inch, "пересчёт при каждом input в БТ/БП",
         size=11, color=MUTED)
    # Big number — centered vertically in card body
    text(c, rx + cw / 2, 4.0 * inch, "$0.05", size=58, color=ACCENT_3, font=FONT_BOLD,
         align="center")
    text(c, rx + cw / 2, 3.5 * inch, "≈ один полный прогон", size=12, color=FG_2,
         align="center")
    # Bullets at the bottom — denser, parallels left card
    yy = 3.0 * inch
    for line in [
        "DeepSeek V3 + Qwen 72B — дефолт",
        "Видно сразу, какая модель сколько съест",
        "На дешёвых: $0.02, на премиум: $0.30",
        "Учитывает per-step переопределения",
    ]:
        c.setFillColor(ACCENT_3)
        c.circle(rx + 0.32 * inch, yy + 0.07 * inch, 0.04 * inch, stroke=0, fill=1)
        text(c, rx + 0.45 * inch, yy + 0.04 * inch, line, size=11, color=FG_2)
        yy -= 0.36 * inch


def slide_tests(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Качество кода — 23 unit-теста",
                 "pytest tests/ — 23/23 PASSED")

    # Big test ratio — fits under subtitle (top ≤ CONTENT_TOP)
    big_top = 5.0 * inch
    big_h = 3.5 * inch
    card(c, 0.65 * inch, big_top - big_h, 4.5 * inch, big_h, border=ACCENT_3)
    c.setFillColor(ACCENT_3)
    c.rect(0.65 * inch, big_top - 0.05 * inch, 4.5 * inch, 0.05 * inch, stroke=0, fill=1)
    text(c, 2.9 * inch, big_top - 1.5 * inch, "23 / 23", size=58, color=ACCENT_3,
         font=FONT_BOLD, align="center")
    text(c, 2.9 * inch, big_top - 2.1 * inch, "PASSED", size=18, color=FG, font=FONT_BOLD,
         align="center")
    text(c, 2.9 * inch, big_top - 2.5 * inch, "pytest tests/  ·  0.10 сек весь suite",
         size=10, color=MUTED, align="center", font=FONT_MONO)

    # Coverage areas
    rx = 5.5 * inch
    text(c, rx, big_top - 0.3 * inch, "ЧТО ПОКРЫТО", size=10, color=MUTED, font=FONT_BOLD)

    items = [
        ("test_parser.py", "10 кейсов", "разные header levels, backslashes,\nдедупликация, пустые блоки, inner backticks"),
        ("test_validators.py", "13 кейсов", "извлечение ID с разными тире,\nпарсинг русско/анг таблиц,\nсортировка ID численно (ФТ-02 < ФТ-10)"),
    ]
    yy = big_top - 0.7 * inch
    for fname, count, desc in items:
        text(c, rx, yy, fname, size=14, color=ACCENT_2, font=FONT_MONO)
        text(c, rx + 2.3 * inch, yy, count, size=11, color=ACCENT_3, font=FONT_BOLD)
        yy -= 0.32 * inch
        for ln in desc.split("\n"):
            text(c, rx + 0.1 * inch, yy, ln, size=11, color=FG_2)
            yy -= 0.25 * inch
        yy -= 0.18 * inch


def slide_demo_a(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Демо A — Веб-калькулятор",
                 "QuickCalc · реальный прогон через UI · 26 апр 2026")

    # Stats row — real numbers from job 7709e2dcca16
    stats = [
        ("5", "БТ", "(4 обяз.)"),
        ("4", "юз-кейса", ""),
        ("7", "ФТ", "100% покрыто"),
        ("12", "файлов", "code + docs + tests"),
        ("$0.02", "стоимость", "27K токенов"),
        ("3.4 мин", "время", "с self-check"),
    ]
    sw = (W - 1.3 * inch - 1.0 * inch) / 6
    by = 3.7 * inch
    for i, (n, lbl, sub) in enumerate(stats):
        x = 0.65 * inch + (sw + 0.2 * inch) * i
        is_highlight = "100%" in sub
        if is_highlight:
            card(c, x, by, sw, 1.5 * inch, border=ACCENT_3)
        else:
            card(c, x, by, sw, 1.5 * inch)
        col = ACCENT_3 if is_highlight else ACCENT
        text(c, x + sw / 2, by + 1.0 * inch, n, size=22, color=col, font=FONT_BOLD,
             align="center")
        text(c, x + sw / 2, by + 0.6 * inch, lbl, size=10, color=FG_2, align="center",
             font=FONT_BOLD)
        if sub:
            text(c, x + sw / 2, by + 0.3 * inch, sub, size=8, color=MUTED, align="center")

    # Two-column: files left, self-check timeline right
    text(c, 0.65 * inch, 3.2 * inch, "СГЕНЕРИРОВАННЫЕ ФАЙЛЫ", size=10, color=MUTED,
         font=FONT_BOLD)

    files = [
        ("src/index.html", "1.7 KB · точка входа"),
        ("src/app.js", "1.2 KB · bootstrap"),
        ("src/calculator.js", "5.8 KB · 14 @implements"),
        ("src/keyboard.js", "1.4 KB · 1 @implements"),
        ("src/styles.css", "3.9 KB · тёмная тема"),
        ("tests/calculator.test.js", "7.3 KB · 18 it()"),
        ("tests/keyboard.test.js", "2.1 KB · 4 it()"),
    ]
    yy = 2.85 * inch
    for path, desc in files:
        c.setFillColor(ACCENT)
        c.circle(0.85 * inch, yy + 0.07 * inch, 0.04 * inch, stroke=0, fill=1)
        text(c, 1.0 * inch, yy + 0.04 * inch, path, size=11, color=ACCENT_2, font=FONT_MONO)
        text(c, 4.0 * inch, yy + 0.04 * inch, desc, size=11, color=FG_2)
        yy -= 0.3 * inch

    # Right column — pipeline timeline with REAL durations
    rx = 7.5 * inch
    text(c, rx, 3.2 * inch, "ХРОНОМЕТРАЖ", size=10, color=MUTED, font=FONT_BOLD)
    timeline = [
        ("use_cases", "31.9s", ACCENT_3, "OK · first try"),
        ("nfr", "22.4s", ACCENT_3, "OK · first try"),
        ("fr", "100.9s", WARN, "retry 1 — нашёл missing БТ-05"),
        ("code", "~60s", ACCENT_3, "OK · 14 @implements"),
        ("tests", "~50s", ACCENT_3, "OK · Vitest + happy-dom"),
        ("readme", "~15s", ACCENT_3, "OK"),
    ]
    yy = 2.85 * inch
    for step, dur, col, status in timeline:
        c.setFillColor(col)
        c.circle(rx + 0.1 * inch, yy + 0.07 * inch, 0.05 * inch, stroke=0, fill=1)
        text(c, rx + 0.3 * inch, yy + 0.04 * inch, step, size=11, color=FG, font=FONT_MONO)
        text(c, rx + 1.5 * inch, yy + 0.04 * inch, dur, size=11, color=col, font=FONT_BOLD)
        text(c, rx + 2.4 * inch, yy + 0.04 * inch, status, size=10, color=FG_2)
        yy -= 0.3 * inch


def slide_demo_bc(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Задания B + C",
                 "один пайплайн — три абсолютно разных приложения")

    # Two big columns — top edge ≤ CONTENT_TOP
    cw = (W - 1.3 * inch - 0.5 * inch) / 2
    card_top = 5.0 * inch
    card_bottom = 0.85 * inch
    ch = card_top - card_bottom  # = 4.15"

    def task_card(x, y, label, name, color, items):
        card(c, x, y, cw, ch, border=color)
        c.setFillColor(color)
        c.rect(x, y + ch - 0.05 * inch, cw, 0.05 * inch, stroke=0, fill=1)
        text(c, x + 0.25 * inch, y + ch - 0.4 * inch, label,
             size=10, color=color, font=FONT_BOLD)
        text(c, x + 0.25 * inch, y + ch - 0.75 * inch, name,
             size=22, color=FG, font=FONT_BOLD)
        yy = y + ch - 1.25 * inch
        for it in items:
            c.setFillColor(color)
            c.circle(x + 0.32 * inch, yy + 0.07 * inch, 0.04 * inch, stroke=0, fill=1)
            text(c, x + 0.45 * inch, yy + 0.04 * inch, it, size=11, color=FG_2)
            yy -= 0.34 * inch

    task_card(0.65 * inch, card_bottom, "B · СРЕДНЕЕ", "TaskBoard", ACCENT_2, [
        "Канбан-доска с тремя статусами",
        "Drag-and-drop между колонками",
        "Создание / удаление задач",
        "Фильтрация по статусу",
        "Сохранение в localStorage",
        "Подтверждение удаления",
    ])

    task_card(0.65 * inch + cw + 0.5 * inch, card_bottom, "C · СЛОЖНОЕ",
              "CurrencyX", ACCENT_3, [
        "12 валют (USD, EUR, RUB, GBP, JPY...)",
        "Курсы из открытого API без ключа",
        "Кеш в localStorage с TTL 1 час",
        "Мгновенный пересчёт по input",
        "Кнопка swap — поменять валюты местами",
        "Fallback: «курс от [дата]» при offline",
    ])


def slide_summary(c: canvas.Canvas) -> None:
    fill_bg(c)
    page_header(c, "Итоги", "что мы построили — в цифрах")

    # Big numbers row — colored variety, real metrics
    stats = [
        ("4", "волны разработки", ACCENT),
        ("23", "API endpoint", ACCENT_2),
        ("12", "LLM моделей", ACCENT_3),
        ("23 / 23", "unit-теста pass", ACCENT_3),
        ("100%", "БТ → ФТ покрытие", WARN),
    ]
    sw = (W - 1.3 * inch - 0.8 * inch) / 5
    yy = 3.5 * inch
    for i, (n, lbl, col) in enumerate(stats):
        x = 0.65 * inch + (sw + 0.2 * inch) * i
        card(c, x, yy, sw, 1.6 * inch, border=col)
        # Adjust font size for narrow display strings like "23 / 23"
        font_size = 30 if "/" in n else 38
        text(c, x + sw / 2, yy + 1.05 * inch, n, size=font_size, color=col, font=FONT_BOLD,
             align="center")
        text(c, x + sw / 2, yy + 0.45 * inch, lbl, size=10, color=FG_2, align="center",
             font=FONT_BOLD)

    # Waves recap
    yy = 3.0 * inch
    text(c, 0.65 * inch, yy, "ЭТАПЫ", size=10, color=MUTED, font=FONT_BOLD)
    yy -= 0.4 * inch
    waves = [
        ("Wave 1", "MVP pipeline + persona prompts + self-check + tests", ACCENT),
        ("Wave 2", "refinement + parallelism + streaming + per-step models", ACCENT_2),
        ("Wave 3", "live preview + traceability matrix + history + cost estimator", ACCENT_3),
    ]
    for tag, desc, col in waves:
        c.setFillColor(col)
        c.roundRect(0.65 * inch, yy - 0.05 * inch, 0.9 * inch, 0.3 * inch, 4, stroke=0, fill=1)
        c.setFillColor(BG)
        c.setFont(FONT_BOLD, 11)
        c.drawCentredString(0.65 * inch + 0.45 * inch, yy + 0.04 * inch, tag)
        text(c, 1.7 * inch, yy + 0.05 * inch, desc, size=12, color=FG_2)
        yy -= 0.45 * inch

    # Tagline filling the space between waves and footer
    text(c, W / 2, 1.05 * inch,
         "open-source  ·  pull requests welcome",
         size=12, color=MUTED, align="center", font=FONT_MONO)

    # Links footer
    yy = 0.6 * inch
    c.setStrokeColor(BORDER)
    c.line(0.65 * inch, yy + 0.3 * inch, W - 0.65 * inch, yy + 0.3 * inch)
    text(c, 0.65 * inch, yy, "github.com/RC6HEX/cascade", size=13, color=ACCENT,
         font=FONT_MONO)
    text(c, W - 0.65 * inch, yy, "rc6hex.github.io/cascade  —  live demo",
         size=12, color=FG_2, font=FONT_MONO, align="right")


# ============== build ==============

SLIDES = [
    ("title", slide_title),
    ("problem", slide_problem),
    ("idea", slide_idea),
    ("cascade", slide_cascade),
    ("architecture", slide_architecture),
    ("stack", slide_stack),
    ("models", slide_models),
    ("personas", slide_personas),
    ("selfcheck", slide_selfcheck),
    ("streaming", slide_streaming),
    ("parallel", slide_parallel),
    ("refine", slide_refine),
    ("traceability", slide_traceability),
    ("perstep", slide_perstep),
    ("history_cost", slide_history_cost),
    ("tests", slide_tests),
    ("demo_a", slide_demo_a),
    ("demo_bc", slide_demo_bc),
    ("summary", slide_summary),
]


def build(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=PAGE)
    c.setTitle("Cascade — автономный генератор приложений")
    c.setAuthor("RC6HEX")
    c.setSubject("Презентация проекта Cascade")
    total = len(SLIDES)
    for n, (name, fn) in enumerate(SLIDES, 1):
        try:
            fn(c)
        except Exception as e:
            print(f"Error on slide {n} ({name}): {e}")
            raise
        if n != 1:
            # Don't double-show URL on the summary slide that has its own
            # explicit footer with the same link.
            page_number(c, n, total, show_url=(name != "summary"))
        c.showPage()
    c.save()
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    print(f"OK Built {out} - {total} slides, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    out = Path(__file__).parent / "cascade.pdf"
    build(out)
