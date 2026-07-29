#!/usr/bin/env python3
"""
Re-extract text for data sheet PDFs using column-aware pdfplumber extraction.

The CM Hammar product data sheets use a two-column layout. The original
scraping used pdfplumber's default extract_text() which interleaves both
columns into garbled output. This script re-reads the already-cached PDFs
using a column-split approach and updates products.json in place.

Usage:
    python reextract_data_sheets.py
"""

import json
import os
import re
import sys

PRODUCTS_PATH = os.path.join("output", "products.json")
PDF_BASE = "output"


def words_to_text(words):
    if not words:
        return ""
    ws = sorted(words, key=lambda w: (round(w["top"] / 3) * 3, w["x0"]))
    lines, cur = [], [ws[0]]
    for w in ws[1:]:
        if abs(w["top"] - cur[-1]["top"]) < 5:
            cur.append(w)
        else:
            lines.append(" ".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
            cur = [w]
    lines.append(" ".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
    return "\n".join(lines)


def extract_page(page):
    try:
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
    except Exception:
        return page.extract_text() or ""
    if not words:
        return page.extract_text() or ""
    mid = page.width / 2
    left = [w for w in words if w["x1"] <= mid + 5]
    right = [w for w in words if w["x0"] >= mid - 5]
    if len(left) >= 10 and len(right) >= 10:
        lt = words_to_text(left).strip()
        rt = words_to_text(right).strip()
        if lt and rt:
            return lt + "\n" + rt
    return page.extract_text() or ""


def extract_pdf(path):
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            chunks = [extract_page(p) for p in pdf.pages]
        text = "\n".join(chunks).strip()
        if text:
            return text
    except Exception as e:
        print(f"  pdfplumber error: {e}")
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        text = "\n".join(p.extract_text() or "" for p in reader.pages).strip()
        return text or None
    except Exception as e:
        print(f"  PyPDF2 error: {e}")
    return None


def is_data_sheet(name):
    return any(k in name.lower() for k in ["data sheet", "product data", "technical data"])


def main():
    with open(PRODUCTS_PATH, encoding="utf-8") as f:
        products = json.load(f)

    updated = 0
    seen_paths = set()  # avoid re-processing shared PDFs twice

    for product in products:
        for section in ("downloads", "approvals"):
            for item in product.get(section, []):
                if not is_data_sheet(item.get("name", "")):
                    continue
                local_path = item.get("local_path")
                if not local_path:
                    continue
                if local_path in seen_paths:
                    continue
                seen_paths.add(local_path)

                full_path = os.path.join(PDF_BASE, local_path)
                if not os.path.exists(full_path):
                    print(f"  Missing: {full_path}")
                    continue

                print(f"Re-extracting: {item['name'][:65]}")
                new_text = extract_pdf(full_path)
                if new_text:
                    # Update all items that reference this PDF
                    for p2 in products:
                        for sec2 in ("downloads", "approvals"):
                            for it2 in p2.get(sec2, []):
                                if it2.get("local_path") == local_path:
                                    it2["text"] = new_text
                    updated += 1

    print(f"\nRe-extracted {updated} unique data sheet PDFs")
    with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    print("Saved products.json")


if __name__ == "__main__":
    main()
