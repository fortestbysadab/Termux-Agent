"""pdfkit — a tiny, dependency-free PDF writer that can actually draw.

Standard-library only (``zlib`` + ``pathlib``) so it runs on Termux with no
pip install. It covers what a report needs:

* Base-14 Helvetica text with real metric-based wrapping and alignment
* tables with header fills, zebra rows, grid lines and right-aligned numbers
* **vector** bar charts (axes, gridlines, value labels, category labels)
* rules, boxes, footers and page numbers, multiple pages

The object graph is assembled with correct numbering: page objects are created
first, then ``/Pages`` is back-patched with their real ids. (A ``/Pages`` tree
pointing at a content stream is the classic hand-rolled-PDF bug — viewers then
report ``Page size: 0 x 0`` and render nothing.)

Usage
-----
    from pdfkit import Canvas

    doc = Canvas(title="Report", footer="Generated locally")
    doc.title("Global Coffee Production Report")
    doc.paragraph("Coffee is ...")
    doc.table(x=56, y=180, width=483, headers=[...], rows=[...])
    doc.bar_chart(x=56, y=360, width=483, height=210, data=[...])
    doc.save("report.pdf")
"""

from __future__ import annotations

import re
import zlib
from pathlib import Path
from typing import Iterable, Sequence

PAGE_SIZES = {
    "A4": (595.28, 841.89),
    "LETTER": (612.0, 792.0),
}

# Helvetica advance widths (1/1000 em) for ASCII 32..126 — the values from the
# standard AFM. Bold is measured as Helvetica x 1.05, which over-estimates
# slightly and therefore never overflows.
HELVETICA_WIDTHS = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]

# WinAnsi (cp1252) byte for the handful of non-ASCII glyphs worth supporting.
WINANSI = {
    "\u2013": 0x96, "\u2014": 0x97, "\u2018": 0x91, "\u2019": 0x92,
    "\u201c": 0x93, "\u201d": 0x94, "\u2022": 0x95, "\u2026": 0x85,
    "\u00b0": 0xB0, "\u00b1": 0xB1, "\u00d7": 0xD7, "\u00b7": 0xB7,
}


def _encode(text: str) -> bytes:
    out = bytearray()
    for ch in str(text):
        if ch in WINANSI:
            out.append(WINANSI[ch])
        elif ord(ch) < 256:
            out.append(ord(ch))
        else:
            out.append(ord("?"))
    return bytes(out)


def text_width(text: str, size: float, bold: bool = False) -> float:
    """Width of `text` in points at `size` pt."""
    total = 0
    for ch in str(text):
        code = ord(ch)
        if 32 <= code <= 126:
            total += HELVETICA_WIDTHS[code - 32]
        elif ch in WINANSI:
            total += 556
        else:
            total += 556
    width = total * size / 1000.0
    return width * 1.05 if bold else width


def wrap_text(text: str, width: float, size: float, bold: bool = False) -> list[str]:
    """Greedy word wrap that respects the font metrics."""
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if text_width(candidate, size, bold) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)

    # break anything still too long (URLs, long tokens)
    out: list[str] = []
    for line in lines:
        while text_width(line, size, bold) > width and len(line) > 1:
            cut = len(line)
            while cut > 1 and text_width(line[:cut], size, bold) > width:
                cut -= 1
            out.append(line[:cut])
            line = line[cut:]
        out.append(line)
    return out


def ellipsize(text: str, width: float, size: float, bold: bool = False) -> str:
    """Trim with an ellipsis so a label never bleeds into its neighbours."""
    if text_width(text, size, bold) <= width:
        return str(text)
    out = str(text)
    while out and text_width(out + "\u2026", size, bold) > width:
        out = out[:-1]
    return (out + "\u2026") if out else ""


class Canvas:
    """A single- or multi-page PDF being built up with drawing calls."""

    def __init__(
        self,
        size: str = "A4",
        margins: tuple[float, float, float, float] = (56, 56, 56, 56),
        title: str = "",
        author: str = "Termux Agent",
        footer: str = "",
    ):
        self.width, self.height = PAGE_SIZES[size.upper()] if isinstance(size, str) else size
        self.left, self.right, self.top, self.bottom = margins
        self.doc_title = title
        self.author = author
        self.footer = footer
        self.pages: list[list[str]] = []
        self._ops: list[str] = []
        self._new_page()

    # ---------------------------------------------------------------- pages
    def _new_page(self) -> None:
        if self._ops:
            self._decorate(self.pages.__len__())
            self.pages.append(self._ops)
        self._ops = []

    def new_page(self) -> None:
        self._new_page()

    def _decorate(self, index: int) -> None:
        """Footer rule, footer text and page number on every finished page."""
        y = self.bottom - 14
        self.line(self.left, y + 12, self.width - self.right, y + 12, width=0.5, gray=0.82)
        if self.footer:
            self.text(self.left, y, _ellipsize_ascii(self.footer, self.content_width, 8),
                      size=8, gray=0.45)
        label = f"{index + 1}"
        self.text(self.width - self.right - text_width(label, 8), y, label, size=8, gray=0.45)

    @property
    def content_width(self) -> float:
        return self.width - self.left - self.right

    def save(self, path: str | Path) -> Path:
        if self._ops:
            self._decorate(len(self.pages))
            self.pages.append(self._ops)
            self._ops = []

        objs: list[bytes] = []

        def add(body: bytes | str) -> int:
            objs.append(body.encode("latin-1") if isinstance(body, str) else body)
            return len(objs)

        catalog_id = add(b"")            # 1 — patched below
        pages_id = add(b"")              # 2 — patched below
        font_regular = add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        )
        font_bold = add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
        )
        font_italic = add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>"
        )
        info_id = add(
            _dict({
                "Title": self.doc_title,
                "Author": self.author,
                "Producer": "pdfkit (stdlib)",
                "Creator": "Termux Agent",
            })
        )

        page_ids: list[int] = []
        for ops in self.pages:
            payload = zlib.compress("\n".join(ops).encode("latin-1"), 9)
            stream_id = add(
                b"<< /Length " + str(len(payload)).encode() + b" /Filter /FlateDecode >>\nstream\n"
                + payload + b"\nendstream"
            )
            page_id = add(
                _dict({
                    "Type": "^/Page",
                    "Parent": f"{pages_id} 0 R",
                    "MediaBox": f"[0 0 {self.width:.2f} {self.height:.2f}]",
                    "Resources": (
                        f"<< /Font << /F1 {font_regular} 0 R /F2 {font_bold} 0 R "
                        f"/F3 {font_italic} 0 R >> >>"
                    ),
                    "Contents": f"{stream_id} 0 R",
                })
            )
            page_ids.append(page_id)

        kids = " ".join(f"{pid} 0 R" for pid in page_ids)
        objs[pages_id - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
        objs[catalog_id - 1] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode()

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for index, body in enumerate(objs, start=1):
            offsets.append(len(out))
            out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

        xref_at = len(out)
        out += f"xref\n0 {len(objs) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for offset in offsets[1:]:
            out += f"{offset:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {len(objs) + 1} /Root {catalog_id} 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n"
        ).encode()

        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(out))
        return target

    # --------------------------------------------------------------- shapes
    @staticmethod
    def _rgb(color: Sequence[float] | None) -> str:
        if color is None:
            return ""
        r, g, b = color
        return f"{r:.3f} {g:.3f} {b:.3f} rg "

    @staticmethod
    def _gray(gray: float) -> str:
        return f"{gray:.3f} g "

    def rect(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        *,
        fill: Sequence[float] | None = None,
        gray: float | None = None,
        stroke_gray: float | None = None,
        stroke_width: float = 0.6,
    ) -> None:
        parts = ["q"]
        if fill is not None:
            parts.append(self._rgb(fill))
        elif gray is not None:
            parts.append(self._gray(gray))
        if stroke_gray is not None:
            parts.append(f"{stroke_gray:.3f} G {stroke_width:.2f} w")
        parts.append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re")
        if fill is not None or gray is not None:
            parts.append("f")
        if stroke_gray is not None:
            parts.append("S")
        parts.append("Q")
        self._ops.append(" ".join(parts))

    def line(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        *,
        width: float = 0.8,
        gray: float = 0.0,
        color: Sequence[float] | None = None,
        dash: tuple[float, float] | None = None,
    ) -> None:
        parts = ["q"]
        parts.append(
            (self._rgb(color) if color else f"{gray:.3f} G")
            + f" {width:.2f} w 1 J"
        )
        if dash:
            parts.append(f" [{dash[0]:.2f} {dash[1]:.2f}] 0 d")
        parts.append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q")
        self._ops.append(" ".join(parts))

    # ----------------------------------------------------------------- text
    def text(
        self,
        x: float,
        y: float,
        value: str,
        *,
        size: float = 10,
        bold: bool = False,
        italic: bool = False,
        gray: float = 0.0,
        color: Sequence[float] | None = None,
        align: str = "left",
        width: float | None = None,
        char_space: float = 0,
    ) -> float:
        """Draw one line. Returns the width consumed."""
        font = "/F2" if bold else "/F3" if italic else "/F1"
        painter = f"{self._rgb(color)}" if color else f"{gray:.3f} g "
        if char_space:
            painter += f"{char_space:.2f} Tc "
        span = text_width(value, size, bold) + char_space * max(0, len(value) - 1)
        if align == "right" and width is not None:
            x = x + width - span
        elif align == "center" and width is not None:
            x = x + (width - span) / 2
        self._ops.append(
            f"BT {painter}{font} {size:.2f} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm "
            f"({_pdf_string(value)}) Tj ET"
        )
        return span

    def paragraph(
        self,
        text: str,
        x: float | None = None,
        y: float | None = None,
        *,
        width: float | None = None,
        size: float = 10,
        leading: float | None = None,
        bold: bool = False,
        italic: bool = False,
        gray: float = 0.0,
        align: str = "left",
    ) -> float:
        """Wrapped paragraph. Returns the y baseline below the last line."""
        x = self.left if x is None else x
        y = (self.height - self.top) if y is None else y
        width = self.content_width if width is None else width
        leading = (size * 1.45) if leading is None else leading
        for line in wrap_text(text, width, size, bold):
            self.text(x, y, line, size=size, bold=bold, italic=italic, gray=gray,
                      align=align, width=width)
            y -= leading
        return y

    def title(self, text: str, *, size: float = 20, y: float | None = None) -> float:
        """Page title plus a rule. Returns the y below it."""
        y = (self.height - self.top - size) if y is None else y
        self.text(self.left, y, text, size=size, bold=True, color=(0.09, 0.11, 0.16))
        y -= 12
        self.line(self.left, y, self.width - self.right, y, width=1.4, color=(0.15, 0.35, 0.62))
        return y - 18

    def heading(self, text: str, *, size: float = 12, y: float) -> float:
        self.text(self.left, y, text, size=size, bold=True, color=(0.13, 0.16, 0.22))
        return y - size - 8

    # ---------------------------------------------------------------- table
    def table(
        self,
        x: float,
        y: float,
        width: float,
        headers: Sequence[str],
        rows: Iterable[Sequence[str]],
        *,
        col_align: Sequence[str] | None = None,
        col_ratios: Sequence[float] | None = None,
        size: float = 9.5,
        row_height: float = 18.0,
        header_fill: Sequence[float] = (0.15, 0.35, 0.62),
        zebra: float = 0.965,
        bold_last_row: bool = False,
    ) -> float:
        """Draw a grid table. Returns the y of the bottom edge."""
        rows = [list(map(str, r)) for r in rows]
        col_align = list(col_align) if col_align else ["left"] * len(headers)
        ratios = list(col_ratios) if col_ratios else [1] * len(headers)
        total = float(sum(ratios))
        widths = [width * r / total for r in ratios]
        pad = 6.0

        # header
        self.rect(x, y - row_height, width, row_height, fill=header_fill)
        cx = x
        for head, col_w, align in zip(headers, widths, col_align):
            self.text(cx + pad, y - row_height + 5.6, ellipsize(head, col_w - pad * 2, size, True),
                      size=size, bold=True, color=(1, 1, 1), align=align, width=col_w - pad * 2)
            cx += col_w

        cursor = y - row_height
        for index, row in enumerate(rows):
            last = index == len(rows) - 1
            is_total = bold_last_row and last
            if index % 2 == 1:
                self.rect(x, cursor - row_height, width, row_height, gray=zebra)
            if is_total:
                self.rect(x, cursor - row_height, width, row_height,
                          fill=(0.90, 0.93, 0.97))
            cx = x
            for value, col_w, align in zip(row, widths, col_align):
                self.text(
                    cx + pad, cursor - row_height + 5.4,
                    ellipsize(value, col_w - pad * 2, size, is_total),
                    size=size, bold=is_total, align=align, width=col_w - pad * 2,
                )
                cx += col_w
            cursor -= row_height

        # grid + outer box
        cx = x
        self.rect(x, cursor, width, y - cursor, stroke_gray=0.88, stroke_width=0.6)
        for col_w in widths[:-1]:
            cx += col_w
            self.line(cx, cursor, cx, y, width=0.5, gray=0.88)
        line_y = y
        while line_y > cursor + 0.1:
            self.line(x, line_y, x + width, line_y, width=0.5, gray=0.88)
            line_y -= row_height
        return cursor

    # ---------------------------------------------------------------- chart
    def bar_chart(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        data: Sequence[tuple[str, float]],
        *,
        title: str = "",
        unit: str = "",
        value_fmt: str = "{:,.1f}",
        bar_color: Sequence[float] = (0.19, 0.42, 0.72),
        accent_color: Sequence[float] = (0.90, 0.45, 0.16),
        grid_steps: int = 4,
    ) -> float:
        """Draw a vector bar chart: axes, gridlines, bars, value + category labels.

        Returns the y below the caption. Every bar is drawn from the same series
        as the table, so heights and printed numbers always agree.
        """
        data = [(str(label), float(value)) for label, value in data]
        if not data:
            return y

        axis_left = x + 44
        axis_bottom = y - height + 26
        plot_w = width - 44 - 8
        pad_top = (17 if title else 0) + (12 if unit else 0)
        plot_top = y - pad_top
        plot_h = plot_top - axis_bottom
        top_value = max(v for _, v in data) or 1.0
        scale_max = top_value * 1.18  # headroom for value labels

        cursor = y - 11
        if title:
            self.text(x, cursor, title, size=11, bold=True, color=(0.13, 0.16, 0.22))
            cursor -= 17
        if unit:  # right-aligned so it never collides with the top tick label
            self.text(x, cursor, unit, size=7.8, gray=0.45, align="right", width=width)

        # gridlines + y tick labels
        for step in range(grid_steps + 1):
            frac = step / grid_steps
            gy = axis_bottom + plot_h * frac
            value = scale_max * frac
            self.line(axis_left, gy, axis_left + plot_w, gy,
                      width=0.5, gray=0.90 if step else 0.62,
                      dash=None if step in (0, grid_steps) else (2, 2))
            self.text(axis_left - 8, gy - 2.6, value_fmt.format(value),
                      size=7.5, gray=0.45, align="right", width=0)

        # axes
        self.line(axis_left, axis_bottom, axis_left + plot_w, axis_bottom, width=1.0, gray=0.35)
        self.line(axis_left, axis_bottom, axis_left, plot_top, width=1.0, gray=0.35)

        # bars
        slot = plot_w / len(data)
        bar_w = min(64.0, slot * 0.62)
        peak = max(range(len(data)), key=lambda i: data[i][1])
        for index, (label, value) in enumerate(data):
            bh = (value / scale_max) * plot_h
            bx = axis_left + slot * index + (slot - bar_w) / 2
            color = accent_color if index == peak else bar_color
            self.rect(bx, axis_bottom, bar_w, bh, fill=color)
            self.rect(bx, axis_bottom, bar_w, bh, stroke_gray=0.35, stroke_width=0.4)
            self.text(bx, axis_bottom + bh + 4, value_fmt.format(value),
                      size=7.8, bold=True, align="center", width=bar_w, color=(0.16, 0.18, 0.24))
            self.text(bx + bar_w / 2, axis_bottom - 12,
                      ellipsize(label, slot + 6, 7.6),
                      size=7.6, gray=0.25, align="center", width=0)

        return axis_bottom - 30


def _ellipsize_ascii(value: str, width: float, size: float) -> str:
    return ellipsize(value, width, size)


def _pdf_string(value: str) -> str:
    raw = _encode(value)
    escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return escaped.decode("latin-1")


def _dict(entries: dict[str, str]) -> bytes:
    parts = []
    for key, value in entries.items():
        if value.startswith("^"):        # pre-formed token, e.g. a /Name
            parts.append(f"/{key} {value[1:]}")
        elif value.startswith(("<<", "[")):
            parts.append(f"/{key} {value}")
        elif value.endswith(" 0 R"):
            parts.append(f"/{key} {value}")
        else:
            parts.append(f"/{key} ({_pdf_string(value)})")
    return ("<< " + " ".join(parts) + " >>").encode("latin-1")


def verify(path: str | Path) -> dict:
    """Structural self-check — no external tools needed.

    Confirms the header, that the page tree points at real /Page objects, and
    counts the drawing operators that prove a chart is actually in there.
    """
    raw = Path(path).read_bytes()
    result: dict = {
        "path": str(path),
        "bytes": len(raw),
        "header_ok": raw.startswith(b"%PDF-"),
        "eof_ok": raw.rstrip().endswith(b"%%EOF"),
        "pages": 0,
        "page_tree_ok": False,
        "rect_ops": 0,
        "fill_ops": 0,
        "stroke_ops": 0,
        "line_ops": 0,
        "text_ops": 0,
        "image_objects": raw.count(b"/Subtype /Image"),
    }

    objects = {
        int(m.group(1)): m.group(2)
        for m in re.finditer(rb"(\d+) 0 obj\s*(.*?)\s*endobj", raw, re.S)
    }
    kids: list[int] = []
    for body in objects.values():
        if b"/Type /Pages" in body:
            refs = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
            if refs:
                kids = [int(n) for n in re.findall(rb"(\d+) 0 R", refs.group(1))]
    # every kid must be a real page object, not a stream
    if kids:
        result["pages"] = len(kids)
        result["page_tree_ok"] = all(
            kid in objects
            and b"/Type /Page" in objects[kid]
            and b"stream" not in objects[kid].split(b">>")[0]
            for kid in kids
        )

    for body in objects.values():
        if b"stream" not in body:
            continue
        data = body.split(b"stream", 1)[1].lstrip(b"\r\n").rsplit(b"endstream", 1)[0]
        try:
            content = zlib.decompress(data)
        except zlib.error:
            content = data
        result["rect_ops"] += len(re.findall(rb"[\d.-]+ [\d.-]+ [\d.-]+ [\d.-]+ re", content))
        result["fill_ops"] += len(re.findall(rb"\bf\b", content))
        result["stroke_ops"] += len(re.findall(rb"\bS\b", content))
        result["line_ops"] += len(re.findall(rb"\bl\b", content))
        result["text_ops"] += len(re.findall(rb"\bTj\b", content))

    result["has_chart"] = result["rect_ops"] >= 5 and result["stroke_ops"] >= 3
    return result
