from app.ingest import chunk_segment, split_page_into_segments


def test_chunk_segment_keeps_text():
    text = "A" * 1000 + "\n" + "B" * 1000
    chunks = chunk_segment(text, size=1200, overlap=100)
    assert len(chunks) >= 2
    assert all(chunks)


def test_section_and_clause_detection():
    text = """SECTION C. WAITING PERIOD AND EXCLUSIONS
1. Waiting Periods
Some wording here.
a. Pre-Existing Diseases: Code - Excl01
More wording here.
"""
    segments, section, clause = split_page_into_segments(text, "")
    assert section.startswith("SECTION C")
    assert any("Pre-Existing" in s["clause"] for s in segments)
