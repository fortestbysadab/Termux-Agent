---
name: data-wrangler
title: Data wrangler
description: Inspect, clean and reshape CSV/JSON/uploaded files with stdlib.
when_to_use: The user uploads a file or asks to clean, filter, join, summarise or convert data.
uses: []
tools: [run_terminal_command]
icon: layers
---

# Data wrangler

Uploaded files land in `uploads/` inside this session's workspace. Treat that
directory as the source and never modify it in place — write results to the
workspace root.

## First: look before you compute

```bash
ls -la uploads/
python3 - <<'EOF'
import csv, itertools
with open("uploads/data.csv", newline="", encoding="utf-8", errors="replace") as f:
    reader = csv.reader(f)
    for row in itertools.islice(reader, 6):
        print(row)
EOF
```

Report the shape (rows × columns), the header names, and 3–5 sample values before
transforming anything. Guessing column names is the most common failure here.

## Handling the formats

- **CSV/TSV**: `csv.DictReader`; always pass `newline=""`. Sniff the delimiter
  with `csv.Sniffer` when it isn't obviously a comma.
- **JSON**: `json.load`; if it is a list of objects, convert to a table with a
  stable key order, not `dict` iteration order.
- **XLSX from a user**: read it with `zipfile` + `xml.etree` (`xl/sharedStrings.xml`
  for text cells, `xl/worksheets/sheet1.xml` for rows). Do not install `openpyxl`.
- **Large files**: stream with a generator and write incrementally; never load a
  file bigger than ~50 MB into a list.

## Cleaning checklist

1. Strip whitespace from headers and values; normalise empty strings to `None`.
2. Report and *keep the original count*: how many rows were dropped, and why.
3. Convert numbers with an explicit parse that returns `None` on failure.
4. Deduplicate on a stated key only — say which key in the summary.
5. Write the cleaned output next to the input (`cleaned_data.csv`), plus a short
   `data_notes.md` when anything was dropped or coerced.

## Summarising for the user

Give the shape before and after, the transformations applied, and the file names
produced. If you plotted anything, load the `svg-chart` skill instead of
inventing chart code inline.
