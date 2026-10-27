---
name: report-bundle
title: Report bundle
description: Chart + spreadsheet + PDF in one go, packaged as a ZIP.
when_to_use: The user wants a full report, "everything in one file", or a set of deliverables.
uses: [data-wrangler, svg-chart, xlsx-report, pdf-report]
tools: [run_terminal_command]
icon: bundle
triggers: [bundle, everything, full report, all the files, zip, package, deliverables]
files: []
---

# Report bundle (a skill that calls other skills)

This skill exists to show composition: it pulls in the four skills it needs —
`data-wrangler`, `svg-chart`, `xlsx-report`, `pdf-report` — and orchestrates them.
Their full instructions are already in this context; follow each one exactly
rather than improvising new code.

## Sequence

1. **Source the data.** If the user uploaded files, use `data-wrangler` to read
   `uploads/` and write a cleaned `data_cleaned.csv` in the workspace root. If
   not, state the numbers you are using in one sentence before drawing anything.
2. **Chart** (`svg-chart`) → `report_chart.svg`. One chart, the headline metric.
3. **Spreadsheet** (`xlsx-report`) → `report_data.xlsx`, with the underlying rows
   plus a totals row so the chart is auditable.
4. **Document** (`pdf-report`) → `report.pdf`, 1–2 pages: title, the key numbers,
   what changed, and a pointer to the two supporting files.
5. **Package** everything into `report_bundle.zip`:

   ```bash
   python3 -c "
   import zipfile
   with zipfile.ZipFile('report_bundle.zip','w',zipfile.ZIP_DEFLATED) as z:
       for f in ('report.pdf','report_data.xlsx','report_chart.svg','data_cleaned.csv'):
           try: z.write(f)
           except FileNotFoundError: pass
   "
   ```

6. **Clean up** every generator script (`.tmp/` or `rm -f generate_*.py`) and any
   `test.*` file, then reply with a short table of the four files and one line
   each on what they contain.

## Rules

- Do not restate the sub-skills' instructions to the user; just do the work.
- If one step fails, finish the others and say plainly which deliverable is
  missing and why — a partial bundle beats a silent failure.
- Total workspace size should stay under a few MB. Aggregate rows, don't dump.
