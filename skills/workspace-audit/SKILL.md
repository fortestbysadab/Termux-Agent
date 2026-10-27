---
name: workspace-audit
title: Workspace audit
description: Inventory the session workspace and check every deliverable is real.
when_to_use: The user asks what is in the workspace, whether a file is valid, or to tidy up.
uses: []
tools: [run_terminal_command]
icon: search
triggers: [audit, inventory, tidy, cleanup, clean up, validate, check the files, what is in the workspace]
files: []
---

# Workspace audit

A deliverable that renders nowhere is a failed deliverable. This pass proves each
file is real before you report on it.

## 1. Inventory

```bash
find . -path ./.tmp -prune -o -type f -printf '%10s  %p\n' | sort -k2
```

Group into: **uploads** (user-provided, never modify), **deliverables** (finished
output), **scratch** (generators, `test.*`, `.tmp/`, `__pycache__`).

## 2. Validate each deliverable by type

| Type | Check |
| --- | --- |
| `.xlsx` | `zipfile.ZipFile(f).testzip() is None`, list parts, count `<row` in sheet1 |
| `.pdf` | starts with `%PDF-`, ends with `%%EOF`, count `/Type /Page` |
| `.svg` | `xml.etree.ElementTree.parse(f)` succeeds |
| `.csv` | parse with `csv.reader`, report rows × cols |
| `.png/.jpg` | `f.read(8)` matches the magic bytes |
| `.zip` | `zipfile.ZipFile(f).namelist()` |
| `.json` | `json.load`, then report the top-level type |
| `.py` | `python3 -m py_compile` |

Report a table: file, size, verdict, one detail (rows / pages / elements).

## 3. Offer the cleanup, do not do it silently

List scratch files and say they can be removed. Delete only the ones you created
this turn; never touch anything in `uploads/`.

## 4. Answer

One short paragraph of state ("3 deliverables, all valid, 1 scratch script"),
then the table. If a file is broken, say what is wrong and rebuild it rather than
describing the breakage at length.
