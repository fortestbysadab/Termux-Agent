---
name: pdf-report
title: PDF document
description: Real PDFs with text, tables and vector charts — no reportlab, no LaTeX.
when_to_use: The user wants a report, document, invoice or printable page as PDF.
uses: []
tools: [run_terminal_command]
icon: doc
triggers: [pdf, invoice, letter, certificate, printable, document]
files: [pdf, md, txt]
---

# PDF document

`reportlab`, `weasyprint`, `matplotlib` and `wkhtmltopdf` are not available here
(and take forever to build on a phone). Do **not** hand-assemble PDF objects —
that is how you get an unrenderable file. Use the bundled toolkit:

```python
import sys
sys.path.insert(0, "<this skill's directory>")   # .../skills/pdf-report
from pdfkit import Canvas, verify
```

`pdfkit.py` writes a correct object graph (page objects first, then `/Pages`
back-patched with their real ids), wraps text with real Helvetica metrics, and
draws vector charts. Available calls:

| Call | What it does |
| --- | --- |
| `Canvas(title=, footer=)` | A4 page, 56 pt margins, footer + page numbers |
| `doc.title(text)` | 20 pt title plus a rule; returns the y below it |
| `doc.heading(text, y=)` | section heading |
| `doc.paragraph(text, y=, width=, size=, leading=)` | wrapped body copy; returns next y |
| `doc.table(x, y, width, headers, rows, col_align=[], bold_last_row=)` | grid table with zebra rows |
| `doc.bar_chart(x, y, width, height, data, unit=)` | **vector** bars: axes, gridlines, value labels, category labels |
| `doc.text / rect / line / new_page` | primitives |
| `doc.save(path)` | write the file |

Coordinates are PostScript points with the origin **bottom-left**, so `y`
decreases as you move down the page. Chain the return values:
`y = doc.title(...)` → `y = doc.paragraph(..., y=y)` → `y = doc.table(..., y=y-16)`.

## Rules that keep the output honest

- **The chart must be drawn**, not described: pass the same numbers to
  `bar_chart()` as to `table()`. That is a vector chart — rectangles in the
  content stream, no bitmap, no ASCII art, no "[chart here]".
- **Never truncate labels yourself.** `pdfkit` measures the font and ellipsizes
  only when a label cannot fit. Half-names like "Bra", "Vie", "Col" are a bug.
- **Never fake a chart by printing numbers in a column** and calling it a chart.
- If a required library is genuinely missing, say which one and stop — do not
  ship a PDF that claims to contain something it does not.
- One page holds roughly 700 pt of content; call `doc.new_page()` before
  overflowing the media box.

## Verify before you answer

```python
from pdfkit import verify
print(verify("report.pdf"))
```

Check `header_ok`, `eof_ok`, `page_tree_ok` (must be `true` — a `false` here
means viewers render a blank page), `pages`, and `has_chart` (`rect_ops >= 5`
and `stroke_ops >= 3`). If poppler is installed, also run
`pdfinfo report.pdf` (Page size must not be `0 x 0`) and
`pdftoppm -r 100 -png report.pdf /tmp/page` to look at it yourself.

**Byte size is a weak proof.** A whole vector chart costs ~700 bytes, so a
correct 1-page report is only 2–3 kB. Quote the operator counts
(`rect_ops`, `stroke_ops`, `image_objects: 0`) and the render, not the size.

## When you are done

Report the absolute path, the byte size, that the tool was `pdfkit` (stdlib),
the first 8 bytes (`%PDF-1.4`), the `verify()` output, and one line on what the
chart shows. Remove the generator script only if the user asked for the PDF
alone; otherwise leave both.
