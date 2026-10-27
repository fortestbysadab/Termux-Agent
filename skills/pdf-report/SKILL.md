---
name: pdf-report
title: PDF document
description: Write a multi-page PDF by hand — no reportlab, no LaTeX.
when_to_use: The user wants a report, document, invoice or printable page as PDF.
uses: []
tools: [run_terminal_command]
icon: doc
---

# PDF document

A PDF is a text file with an object table. You can emit one with `print()`.
`reportlab`, `weasyprint` and `wkhtmltopdf` are not available (or take forever to
build), so generate the PDF directly.

## Structure

```python
objects = []
def add(body: bytes) -> int:
    objects.append(body)
    return len(objects)          # object numbers are 1-based

# 1 Catalogue, 2 Pages, 3 Page, 4 Contents (stream), 5 Font
```

The page's `/Contents` stream is a mini drawing language:

| Command | Meaning |
| --- | --- |
| `BT /F1 18 Tf 56 760 Td (Title) Tj ET` | text at a position |
| `0.1 0.1 0.1 rg` | fill colour |
| `56 740 m 540 740 l S` | line from → to, stroke |
| `q ... Q` | save/restore graphics state |

## Layout rules

- Page size `595 842` (A4 points). Margins 56. Body text `11 Tf`, leading 16.
- Wrap text yourself at ~92 characters; **escape `(`, `)` and `\`** in strings.
- One page ≈ 44 lines of body text — start a new page object after that rather
  than overflowing the media box.
- Keep a real `/Font` (`/Helvetica`) and set `/Length` on the content stream to
  its exact byte length, or viewers show a blank page.

## Verify

```bash
python3 - <<'EOF'
data = open("report.pdf","rb").read()
assert data.startswith(b"%PDF-1."), "bad header"
assert data.rstrip().endswith(b"%%EOF"), "truncated"
print(len(data), "bytes,", data.count(b"/Type /Page "), "pages")
EOF
```

Check the byte count is plausible (a one-page text PDF is 2–4 kB). Keep the file
in the workspace root with a descriptive name, remove the generator script, then
tell the user the page count and what is on each page.
