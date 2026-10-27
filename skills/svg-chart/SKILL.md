---
name: svg-chart
title: SVG chart
description: Draw a crisp vector chart with zero dependencies.
when_to_use: The user asks for a chart, graph, plot, dashboard or any visual of numbers.
uses: []
tools: [run_terminal_command]
icon: chart
---

# SVG chart

Never install plotting libraries on this device — they compile for 20+ minutes
on Android ARM64 and time out. Write the SVG by hand instead: it is a handful of
`<rect>`/`<path>` elements, it renders instantly in every browser and previewer,
and it stays sharp at any size.

## Steps

1. **Shape the data first.** Reduce the input to rows of `(label, value)`. Print
   it once (`python3 -c "print(rows)"`) so you can see the numbers before drawing.
2. **Write a generator script** that emits the SVG to a single file in the
   workspace root, named for the deliverable (e.g. `revenue_by_month.svg`).
   Keep the generator in `.tmp/` or run it inline with `python3 -c`.
3. **Draw with a real coordinate system**, not guessed pixels:

   ```python
   W, H, PAD = 720, 320, 44
   plot_h = H - PAD * 2 - 28          # room for axis labels
   vmax = max(v for _, v in rows) or 1
   for i, (label, value) in enumerate(rows):
       h = plot_h * value / vmax
       x = PAD + i * ((W - PAD * 2) / len(rows))
       # rect + label baseline at H - PAD
   ```

4. **Style for both themes.** Set an explicit light background
   (`<rect fill="#fff">`) and dark-enough text (`#16171d`), or the chart will be
   invisible in one of the two themes.
5. **Finish the details that read as quality:** rounded bar corners (`rx="8"`),
   a `<linearGradient>` fill, value labels above each mark, an axis baseline, and
   `font-family="system-ui"` so the type matches the console.
6. **Verify** with `python3 -c "import xml.etree.ElementTree as ET; ET.parse('file.svg')"`
   and `ls -l` — then reply with the file name and what it shows.

## Rules

- No `matplotlib`, `seaborn`, `plotly`, `pandas`, `PIL`.
- One file, workspace root, no `chart.svg`/`test.svg` left behind.
- If the data needs more than ~40 marks, aggregate first — do not draw 500 bars.
