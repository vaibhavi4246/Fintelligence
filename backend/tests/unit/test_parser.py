"""Unit tests for filing parsing helpers."""

from types import SimpleNamespace


def test_parse_pdf_document_structures_sections_and_tables(monkeypatch):
    from app.ingestion import parser

    class FakePage:
        def __init__(self, text, tables):
            self._text = text
            self._tables = tables

        def extract_text(self):
            return self._text

        def extract_tables(self):
            return self._tables

    class FakePdf:
        def __init__(self):
            self.pages = [
                FakePage(
                    "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS\nRevenue increased\nOperating margin improved",
                    [["Metric", "Value"], ["Revenue", "$10B"], ["Margin", "30%"]],
                ),
                FakePage(
                    "ITEM 1A. RISK FACTORS\nSupply chain issues remain a risk",
                    [],
                ),
            ]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(parser, "pdfplumber", SimpleNamespace(open=lambda source: FakePdf()))

    parsed = parser.parse_pdf_document(b"%PDF-1.4 fake")

    assert "Revenue increased" in parsed.text
    assert any(section.section_label == "MD&A" for section in parsed.sections)
    assert any(section.section_label == "Risk Factors" for section in parsed.sections)
    assert len(parsed.tables) == 1
    assert parsed.tables[0].rows[0]["Metric"] == "Revenue"
    assert parsed.tables[0].rows[0]["Value"] == "$10B"