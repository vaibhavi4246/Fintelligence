from app.ingestion.chunker import _ENC, chunk_text


def test_chunk_text_preserves_mdna_overlap_and_section_boundaries():
    mdna_body = " ".join(f"revenue{i}" for i in range(120))
    risk_body = " ".join(f"risk{i}" for i in range(40))
    text = (
        "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS\n\n"
        f"{mdna_body}\n\n"
        "ITEM 1A. RISK FACTORS\n\n"
        f"{risk_body}"
    )

    chunks = chunk_text(text, fiscal_period="Q2-2023", chunk_tokens=40, overlap_tokens=10)
    mdna_chunks = [chunk for chunk in chunks if chunk.section_label == "MD&A"]
    risk_chunks = [chunk for chunk in chunks if chunk.section_label == "Risk Factors"]

    assert len(mdna_chunks) >= 2
    assert risk_chunks
    assert all("risk factors" not in chunk.content.lower() for chunk in mdna_chunks)

    first_tokens = _ENC.encode(mdna_chunks[0].content)
    second_tokens = _ENC.encode(mdna_chunks[1].content)
    assert first_tokens[-10:] == second_tokens[:10]


def test_chunk_text_keeps_tables_atomic():
    table = (
        "| Metric | Value | Change |\n"
        "| --- | --- | --- |\n"
        "| Revenue | $94.8B | -3% |\n"
        "| Gross margin | $42.6B | +2% |\n"
        "| Operating cash flow | $28.6B | +1% |"
    )
    text = (
        "ITEM 2. MANAGEMENT'S DISCUSSION AND ANALYSIS\n\n"
        f"{table}\n\n"
        "Additional commentary follows with enough filler text to exceed a small chunk size."
    )

    chunks = chunk_text(text, fiscal_period="Q2-2023", chunk_tokens=12, overlap_tokens=4)
    table_chunks = [chunk for chunk in chunks if "| Revenue |" in chunk.content]

    assert len(table_chunks) == 1
    assert "| Operating cash flow | $28.6B | +1% |" in table_chunks[0].content
    assert table_chunks[0].section_label == "MD&A"