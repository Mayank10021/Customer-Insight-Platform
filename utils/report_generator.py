"""
Report Generator - Excel (multi-sheet) and PDF summary report builders.
"""
import io
import zipfile
from datetime import datetime
import pandas as pd
from fpdf import FPDF


def _safe(text) -> str:
    """FPDF's core Helvetica font is latin-1 only, so any rupee sign, em-dash,
    or smart quote in a KPI/table value silently crashed PDF generation
    before. Everything rendered into the PDF goes through here first."""
    text = str(text)
    replacements = {
        "\u20b9": "Rs. ", "\u2014": "-", "\u2013": "-",
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2026": "...", "\u2022": "-", "\u00a0": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def build_zip_report(csv_sheets: dict):
    """
    csv_sheets: {"filename_without_ext": dataframe, ...}
    Returns bytes of a .zip containing one .csv per entry. This is the
    correct format for large raw tables (tens/hundreds of thousands of
    rows) — writing the same data into an Excel workbook via openpyxl
    can take over a minute per 100k rows, while CSV-in-ZIP takes a few
    seconds regardless of row count.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, df in csv_sheets.items():
            safe_name = f"{name}.csv"
            content = (df if not df.empty else pd.DataFrame({"Info": ["No data available"]})).to_csv(index=False)
            zf.writestr(safe_name, content)
    buffer.seek(0)
    return buffer.getvalue()


def build_excel_report(sheets: dict):
    """
    sheets: {"Sheet Name": dataframe, ...}
    Returns bytes of an .xlsx file with one tab per DataFrame.
    Uses xlsxwriter (faster than openpyxl for writing) — still not
    appropriate for raw tables with 100k+ rows; callers should export
    those as CSV/ZIP instead (see views/reports.py for the size-based split).
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        for name, df in sheets.items():
            safe_name = name[:31] if name else "Sheet1"
            (df if not df.empty else pd.DataFrame({"Info": ["No data available"]})).to_excel(
                writer, sheet_name=safe_name, index=False
            )
    buffer.seek(0)
    return buffer.getvalue()


class _ReportPDF(FPDF):
    """Branded PDF report: violet header band with a rounded app-icon mark,
    KPI values rendered as small colored cards instead of a plain label:value
    list, and zebra-striped tables with a violet header row."""

    ACCENT = (108, 92, 231)      # #6c5ce7
    ACCENT_2 = (0, 194, 209)     # #00c2d1
    INK = (22, 16, 41)           # #161029
    MUTED = (114, 110, 163)      # #726ea3
    ROW_ALT = (247, 246, 253)    # very light lavender
    BORDER = (230, 227, 247)

    def header(self):
        # Two-tone header band (solid + a thin accent strip) standing in for
        # a violet -> cyan gradient, which flat PDF fills can't do directly.
        self.set_fill_color(*self.INK)
        self.rect(0, 0, 210, 26, style="F")
        self.set_fill_color(*self.ACCENT_2)
        self.rect(0, 26, 210, 1.4, style="F")

        # App-icon mark: rounded violet square with a phone glyph substitute
        self.set_fill_color(*self.ACCENT)
        self.rect(10, 6, 13, 13, style="F", round_corners=True, corner_radius=3.5)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.set_xy(10, 8.5)
        self.cell(13, 8, "CL", align="C")

        self.set_font("Helvetica", "B", 15)
        self.set_xy(28, 6)
        self.cell(0, 8, "CustomerLens", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(200, 197, 224)
        self.set_xy(28, 14)
        self.cell(0, 6, "Mobile Store Intelligence Report")
        self.set_xy(0, 14)
        self.set_font("Helvetica", "", 8)
        self.cell(200, 6, f"Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}", align="R")
        self.set_text_color(0, 0, 0)
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*self.BORDER)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(*self.MUTED)
        self.set_xy(10, -12)
        self.cell(95, 8, "CustomerLens", align="L")
        self.set_xy(105, -12)
        self.cell(95, 8, f"Page {self.page_no()}", align="R")

    def section_title(self, title):
        self.ln(3)
        self.set_fill_color(*self.ACCENT)
        self.rect(10, self.get_y() + 1.5, 3, 5, style="F")
        self.set_font("Helvetica", "B", 12.5)
        self.set_text_color(*self.INK)
        self.set_x(16)
        self.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def kpi_grid(self, kpis: dict):
        """Render KPIs as a grid of small rounded cards (3 per row) instead
        of a plain label: value list."""
        per_row = 3
        gap = 5
        margin = 10
        card_w = (210 - 2 * margin - gap * (per_row - 1)) / per_row
        card_h = 20
        items = list(kpis.items())
        row_y = self.get_y()
        for i, (label, value) in enumerate(items):
            col = i % per_row
            if col == 0 and i > 0:
                row_y += card_h + gap
            x = margin + col * (card_w + gap)
            y = row_y
            self.set_fill_color(*self.ROW_ALT)
            self.set_draw_color(*self.BORDER)
            self.rect(x, y, card_w, card_h, style="DF", round_corners=True, corner_radius=2.5)
            self.set_fill_color(*self.ACCENT)
            self.rect(x, y, 2, card_h, style="F", round_corners=True, corner_radius=1)
            self.set_xy(x + 5, y + 3)
            self.set_font("Helvetica", "", 7.5)
            self.set_text_color(*self.MUTED)
            self.cell(card_w - 8, 5, _safe(str(label).upper())[:26])
            self.set_xy(x + 5, y + 9.5)
            self.set_font("Helvetica", "B", 13)
            self.set_text_color(*self.INK)
            self.cell(card_w - 8, 7, _safe(str(value))[:20])
        self.set_xy(margin, row_y + card_h + 8)

    def styled_table(self, df):
        df_show = df.head(15)
        n_cols = max(len(df_show.columns), 1)
        col_width = 190 / n_cols

        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*self.ACCENT)
        self.set_text_color(255, 255, 255)
        for col in df_show.columns:
            self.cell(col_width, 8, _safe(str(col))[:18], border=0, fill=True, align="C")
        self.ln()

        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self.INK)
        for i, (_, row) in enumerate(df_show.iterrows()):
            self.set_fill_color(*(self.ROW_ALT if i % 2 == 0 else (255, 255, 255)))
            for val in row:
                self.cell(col_width, 7.5, _safe(str(val))[:18], border=0, fill=True)
            self.ln()
        self.set_draw_color(*self.BORDER)
        self.line(10, self.get_y(), 200, self.get_y())


def build_pdf_report(kpis: dict, tables: dict):
    """
    kpis: {"Total Sales": "...", "Revenue": "...", ...}
    tables: {"Section Title": dataframe, ...} (rendered as simple tables, max ~15 rows each)
    Returns bytes of a PDF file.
    """
    pdf = _ReportPDF()
    pdf.add_page()

    pdf.section_title("Executive Summary - Key Performance Indicators")
    pdf.kpi_grid(kpis)

    for title, df in tables.items():
        pdf.section_title(title)

        if df is None or df.empty:
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(0, 8, "No data available", new_x="LMARGIN", new_y="NEXT")
            continue

        pdf.styled_table(df)

    return bytes(pdf.output())
