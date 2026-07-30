"""
Add two SOLAS-Index-required sections to every product HTML page:
  1. Inline certificate details table (cert number, issuer, standards, valid-until)
     inserted after the existing <h3>Approvals</h3> download list.
  2. How It Works section (mechanism description)
     inserted before <h3>Downloads</h3>.
"""
import argparse, json, os, re

PRODUCTS_JSON = os.path.join(os.path.dirname(__file__), "output", "products.json")
SITE_ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# ── Helpers ───────────────────────────────────────────────────────────────────

_STD_PATTERNS = [
    ("SOLAS",  r"SOLAS"),
    ("MED",    r"Marine Equipment Directive|MED\b"),
    ("MCA",    r"\bMCA\b|RedEnsign|UK type"),
    ("USCG",   r"\bUSCG\b|US Coast Guard|160\."),
    ("CCS",    r"\bCCS\b|China Classification"),
    ("DNV",    r"\bDNV\b"),
    ("IECEx",  r"\bIECEx\b"),
    ("ATEX",   r"\bATEX\b"),
    ("IMO",    r"\bIMO\b"),
]


def _extract_standards(cert: dict) -> str:
    """Return short comma-separated standards labels from a cert dict."""
    corpus = " ".join([
        cert.get("certificate_type", ""),
        cert.get("issuing_body", ""),
        " ".join(cert.get("regulations") or []),
    ])
    found = [label for label, pat in _STD_PATTERNS if re.search(pat, corpus, re.I)]
    return " · ".join(found) if found else ""


def _shorten_cert_type(ct: str) -> str:
    ct = ct.strip()
    ct = re.sub(r"CERTIFICATE$", "", ct, flags=re.I).strip()
    # Abbreviate long strings
    ct = ct.replace("TYPE-EXAMINATION (MODULE B)", "Module B")
    ct = ct.replace("TYPE EXAMINATION (MODULE B)", "Module B")
    ct = ct.replace("EC TYPE EXAMINATION", "EC Module B")
    ct = ct.replace("Type Approval", "Type Approval")
    if len(ct) > 40:
        ct = ct[:37] + "…"
    return ct


def build_cert_table(product: dict) -> str:
    """Return HTML for the inline cert details table, or '' if no structured certs."""
    all_items = (product.get("approvals") or []) + (product.get("downloads") or [])
    CERT_TYPES = ("approval_certificate", "approval", "certificate")
    rows = []
    seen_cert_nos = set()

    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict) or s.get("document_type") not in CERT_TYPES:
            continue
        cert_no   = (s.get("certificate_number") or "").strip()
        issuer    = (s.get("issuing_body") or "").strip()
        cert_type = _shorten_cert_type(s.get("certificate_type") or "")
        standards = _extract_standards(s)
        valid     = (s.get("valid_until") or "").strip()

        if not cert_no and not issuer:
            # Try key_fields for CCS-style certs
            kf = s.get("key_fields") or {}
            cert_no = kf.get("Certificate No.", kf.get("certificate_number", "")).strip()
            # Extract issuing body from summary "issued by X" pattern
            summary = s.get("summary") or ""
            body_m = re.search(r'issued by ([A-Z][^\.]{3,50}?)(?:\s+for|\s+to|\.|$)', summary, re.I)
            if body_m:
                issuer = body_m.group(1).strip()
            else:
                issuer = ""
            # Fall back to item name keyword
            if not issuer:
                item_name = item.get("name", "")
                if "CSS China" in item_name or "CCS" in item_name:
                    issuer = "China Classification Society"
            # Extract standards from summary/name
            if not standards:
                standards = _extract_standards({"regulations": [summary, item.get("name", "")]})


        if not cert_no:
            continue
        if cert_no in seen_cert_nos:
            continue
        seen_cert_nos.add(cert_no)

        rows.append((cert_no, issuer, cert_type, standards, valid))

    if not rows:
        return ""

    header = (
        '<thead><tr style="background:#f0f4f8">'
        + "".join(
            f'<th style="text-align:left;padding:5px 10px;border:1px solid #d8e0ea;white-space:nowrap">{h}</th>'
            for h in ["Cert No.", "Issuing Body", "Type", "Standards", "Valid Until"]
        )
        + "</tr></thead>"
    )
    tbody_rows = ""
    for r in rows:
        cells = "".join(
            f'<td style="padding:5px 10px;border:1px solid #d8e0ea">{c}</td>'
            for c in r
        )
        tbody_rows += f"<tr>{cells}</tr>"

    return (
        '\n<div class="cert-details-inline" style="margin-top:14px;overflow-x:auto">'
        '\n  <h4 style="font-size:0.9em;font-weight:600;color:#445;margin-bottom:6px">Certificate Details</h4>'
        f'\n  <table style="width:100%;font-size:0.82em;border-collapse:collapse;min-width:500px">'
        f"\n    {header}"
        f"\n    <tbody>{tbody_rows}</tbody>"
        "\n  </table>"
        "\n</div>"
    )


def get_mechanism_text(product: dict) -> str:
    """Return the best available mechanism/how-it-works description, or ''."""
    all_items = (product.get("downloads") or []) + (product.get("approvals") or [])
    # Prefer user_manual how_it_works
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict): continue
        if s.get("document_type") == "user_manual":
            hiw = (s.get("how_it_works") or "").strip()
            if hiw and len(hiw) > 40:
                return hiw
    # Fall back to data_sheet DESCRIPTION sentences
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict): continue
        if s.get("document_type") == "data_sheet":
            desc = (s.get("sections") or {}).get("DESCRIPTION", [])
            if isinstance(desc, list):
                clean = [
                    x.strip() for x in desc
                    if isinstance(x, str) and len(x.strip()) > 25
                    and not x.strip().isupper()
                    and not re.match(r"^(Page|Rev|KOM|www\.)", x.strip())
                ]
                if clean:
                    return " ".join(clean[:4])
    return ""


# ── HTML patching ─────────────────────────────────────────────────────────────

def _patch_certs(html: str, cert_table_html: str) -> str:
    """Append cert details table after the Approvals <ul>. Idempotent."""
    if "cert-details-inline" in html:
        return html  # already patched
    if not cert_table_html:
        return html

    # Find the Approvals section closing </ul>
    m = re.search(
        r'(<h3[^>]*>Approvals</h3>.*?</ul>)',
        html, re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return html

    insert_at = m.end()
    return html[:insert_at] + cert_table_html + html[insert_at:]


def _patch_mechanism(html: str, mechanism: str) -> str:
    """Insert How It Works section before <h3>Downloads</h3>. Idempotent."""
    if "product-mechanism" in html:
        return html  # already patched
    if not mechanism:
        return html

    # Truncate very long descriptions to ~600 chars at a sentence boundary
    if len(mechanism) > 600:
        cut = mechanism[:600]
        last_dot = cut.rfind(".")
        mechanism = (cut[:last_dot + 1] if last_dot > 300 else cut) + " …"

    block = (
        '\n<h3>How It Works</h3>'
        f'\n<p class="product-mechanism" style="font-size:0.9em;line-height:1.6;color:#333;margin-bottom:12px">'
        f'{mechanism}'
        '</p>'
    )

    m = re.search(r'<h3[^>]*>Downloads</h3>', html, re.IGNORECASE)
    if not m:
        return html

    return html[:m.start()] + block + "\n" + html[m.start():]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        products = json.load(f)

    by_sku = {p["sku"].upper(): p for p in products}
    catalogue_dir = os.path.join(SITE_ROOT, "catalogue")

    updated = skipped = 0

    for slug in sorted(os.listdir(catalogue_dir)):
        sku = slug.upper()
        html_path = os.path.join(catalogue_dir, slug, "index.html")
        if not os.path.isdir(os.path.join(catalogue_dir, slug)):
            continue
        if not os.path.exists(html_path):
            continue

        product = by_sku.get(sku)
        if not product:
            continue

        with open(html_path, encoding="utf-8") as f:
            original = f.read()

        cert_table = build_cert_table(product)
        mechanism  = get_mechanism_text(product)

        html = _patch_certs(original, cert_table)
        html = _patch_mechanism(html, mechanism)

        if html == original:
            skipped += 1
            continue

        added = []
        if cert_table and "cert-details-inline" in html and "cert-details-inline" not in original:
            added.append("cert-table")
        if mechanism and "product-mechanism" in html and "product-mechanism" not in original:
            added.append("mechanism")

        print(f"  [updated] {sku} — {added}")
        updated += 1

        if not args.dry_run:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)

    print(f"\nDone — {updated} pages updated, {skipped} unchanged.")


if __name__ == "__main__":
    main()
