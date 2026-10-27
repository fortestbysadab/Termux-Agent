---
name: xlsx-report
title: Excel workbook
description: Produce a real .xlsx with formatting, using only zipfile.
when_to_use: The user wants a spreadsheet, tracker, plan, budget or schedule as a file.
uses: []
tools: [run_terminal_command]
icon: table
---

# Excel workbook

An `.xlsx` is a ZIP of XML parts. Writing those parts by hand takes ~60 lines and
0.2 seconds; `pip install openpyxl` on this device takes minutes or fails. Do not
install anything — write the parts.

## Minimum viable workbook

```python
import zipfile, io

def cell(ref, value, style=0):
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{value}</t></is></c>'
```

Files to write into the zip (all required):

| Part | Purpose |
| --- | --- |
| `[Content_Types].xml` | declares workbook + sheet + styles |
| `_rels/.rels` | points at `xl/workbook.xml` |
| `xl/workbook.xml` | sheet names and ids |
| `xl/_rels/workbook.xml.rels` | sheet → `worksheets/sheet1.xml` |
| `xl/worksheets/sheet1.xml` | the rows |
| `xl/styles.xml` | fonts/fills/borders referenced by `s="N"` |

## Quality bar

- **Header row bold on a tinted fill**, frozen so it stays visible:
  `<sheetView><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView>`.
- **Column widths** set to fit content (`<cols><col min="1" max="1" width="22" customWidth="1"/></cols>`).
- **Real numbers, not strings** — a `t="inlineStr"` cell holding "42" will not sum.
- Use `inlineStr` (as above) so you don't need a shared-strings part at all.

## Verify before replying

```bash
python3 - <<'EOF'
import zipfile
z = zipfile.ZipFile("plan.xlsx")
print(z.namelist())
print(z.testzip())          # None means every part is intact
EOF
```

Then confirm the row count matches what was asked. Name the file for the
deliverable (`q3_budget.xlsx`), keep it in the workspace root, delete any
`generate_*.py` helper, and check the console's preview renders it (the backend
parses xlsx with zipfile + xml.etree, so a malformed part shows up immediately).
