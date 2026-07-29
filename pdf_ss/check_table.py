"""Inspect pdfplumber table extraction on data sheet PDFs."""
import pdfplumber, json, re, os

PDFS = [
    ("H20 ERU",  "output/pdfs/_shared/76307372c1_KOM-3056-v.2.0-Product-Data-Sheet-H20-ERU.pdf"),
    ("H20 HRU",  "output/pdfs/_shared/061de5b791_KOM-2454-v.2.0-Product-Data-Sheet-H20-HRU-for-Raft.pdf"),
    ("HPS",      "output/pdfs/_shared/dbf792e95b_KOM-4026-v.1.0-Product-Data-Sheet-for-Hydrostatic-Pressure-Switch-.pdf"),
    ("Inflator", "output/pdfs/_shared/5abacf8086_KOM-2447-v.2.0-Product-Data-Sheet-Lifejacket-Inflator-A1.pdf"),
]

for label, path in PDFS:
    if not os.path.exists(path):
        print(f"MISSING: {path}")
        continue
    print(f"\n{'='*60}")
    print(f"=== {label} ===")
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if "SPECIFICATION" not in text.upper():
                continue
            print(f"\n--- Page {page_num} words near SPECIFICATIONS ---")
            # Try word extraction split at mid-page
            mid = page.width / 2
            left_words  = page.extract_words(x_tolerance=3, y_tolerance=3)
            print(f"  Page width: {page.width}, mid: {mid}")

            # Group words by y-position (line)
            lines = {}
            for w in left_words:
                y = round(w['top'] / 4) * 4  # bucket by ~4 pts
                if y not in lines:
                    lines[y] = []
                lines[y].append(w)

            # Find the SPECIFICATIONS heading line
            spec_y = None
            for y, words in sorted(lines.items()):
                text_line = " ".join(w['text'] for w in words)
                if re.search(r'SPECIFICATIONS', text_line, re.I):
                    spec_y = y
                    print(f"  SPEC heading at y~{y}: {text_line!r}")

            # Print the next 12 lines after that
            if spec_y:
                in_spec = False
                count = 0
                for y, words in sorted(lines.items()):
                    if y >= spec_y:
                        in_spec = True
                    if in_spec:
                        cols = [(round(w['x0']), w['text']) for w in words]
                        print(f"  y={y:4d}: {cols}")
                        count += 1
                    if count > 15:
                        break

            # Also try pdfplumber's built-in table extractor
            tables = page.extract_tables()
            if tables:
                print(f"\n  pdfplumber tables found: {len(tables)}")
                for i, t in enumerate(tables):
                    print(f"  Table {i}: {t}")
