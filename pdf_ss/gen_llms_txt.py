"""Generate llms.txt from products.json using all available structured data."""
import json, os, sys

# Reuse the same extraction function from patch_product_pages.py
sys.path.insert(0, os.path.dirname(__file__))
from patch_product_pages import extract_ds_fields

PRODUCTS_JSON  = os.path.join(os.path.dirname(__file__), "output", "products.json")
OUT_FILE       = os.path.join(os.path.dirname(__file__), "..", "llms.txt")
BASE_URL       = "https://www.cmhammar.com"
CATALOGUE_DIR  = os.path.join(os.path.dirname(__file__), "..", "catalogue")

HEADER = """\
# CM Hammar

> Better Solutions for Safety at Sea. CM Hammar AB is a Swedish manufacturer of marine life-saving appliances: hydrostatic release units (HRU), remote release systems (RRS), and lifejacket inflators certified to SOLAS, MED, USCG, DNV, and MCA standards.

## About

CM Hammar has been manufacturing safety equipment for commercial and recreational vessels for over 30 years. All products comply with SOLAS (Safety of Life at Sea) regulations and carry type approvals from recognized classification societies including Bureau Veritas, DNV, MCA, and Lloyd's Register.

- Website: https://www.cmhammar.com
- Catalogue: https://www.cmhammar.com/catalogue/
- Approvals: https://www.cmhammar.com/approvals/
- Downloads: https://www.cmhammar.com/downloads/
- Where to Buy: https://www.cmhammar.com/distributors/
- Contact: https://www.cmhammar.com/contact-us/

## Product Categories

- **H20 Release Units (HC-series)**: Hydrostatic release units for liferafts, EPIRBs, and MES systems. SOLAS and MED approved.
- **Remote Release Systems (HE-series)**: Electric remote release control, input, and release units (ERRS/MRRS). For bridge-operated release of liferafts.
- **Lifejacket Inflators (HM-series)**: Automatic (MA1-EC) and manual inflator mechanisms. Approved for SOLAS lifejackets.
- **Special Applications (HR-series)**: Polar Box cold-weather HRU housings, ATEX/EX rated equipment, and inspection tools.
- **Inspection Tools (TR-series)**: Testing and inspection equipment for HRU servicing.

## Products
"""

# Ordered display fields — shown in this order when present
DISPLAY_FIELDS = [
    "Activation Depth",
    "Service Life",
    "Operating Temperature",
    "Material",
    "Colour",
    "Weight",
    "Breaking Load",
    "Weak Link Strength",
    "Approved Standards",
    "Certificate Valid Until",
    "Capacity",
    "Voltage",
    "Battery Type",
    "Backup Battery",
    "Dimensions",
    "Inputs",
    "Outputs",
    "Power Supply",
    "Enclosure Protection",
    "Activation Angle",
]

_catalogue_slugs: set[str] = set()

def _known_slugs() -> set[str]:
    global _catalogue_slugs
    if not _catalogue_slugs and os.path.isdir(CATALOGUE_DIR):
        _catalogue_slugs = {
            d.lower() for d in os.listdir(CATALOGUE_DIR)
            if os.path.isdir(os.path.join(CATALOGUE_DIR, d))
        }
    return _catalogue_slugs


def render_product(p: dict) -> str:
    sku      = p.get("sku", "").upper()
    subtitle = p.get("subtitle") or p.get("name") or sku
    slug     = sku.lower()

    if slug in _known_slugs():
        url     = f"{BASE_URL}/catalogue/{slug}/"
        heading = f"### [{sku}]({url})"
    else:
        heading = f"### {sku}"

    lines = [heading, subtitle, ""]

    # -- Original product-page specs (always shown first) --
    page_specs = p.get("specifications") or {}
    shown_keys = set()
    if isinstance(page_specs, dict):
        for k, v in page_specs.items():
            if v:
                lines.append(f"  - **{k}**: {v}")
                shown_keys.add(k.lower())

    # -- Enriched technical fields from all document sources --
    fields = extract_ds_fields(p)
    for fname in DISPLAY_FIELDS:
        if fname in fields and fields[fname]:
            # Skip if an equivalent key was already shown from page specs
            if fname.lower() not in shown_keys:
                lines.append(f"  - **{fname}**: {fields[fname]}")

    # -- Certifications --
    certs = []
    all_items = (p.get("downloads") or []) + (p.get("approvals") or [])
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict):
            continue
        cert_no = s.get("certificate_number") or ""
        issued  = s.get("issued_by") or ""
        scope   = s.get("scope") or item.get("name") or ""
        if cert_no or issued:
            parts = [x for x in [scope[:70], issued, cert_no] if x]
            certs.append(" – ".join(parts))
    if certs:
        lines.append("  Certifications:")
        for c in certs[:4]:
            lines.append(f"    - {c}")

    lines.append("")
    return "\n".join(lines)


def main():
    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        products = json.load(f)

    products.sort(key=lambda p: p.get("sku", "").upper())

    sections = [HEADER]
    for p in products:
        sections.append(render_product(p))

    out_path = os.path.normpath(OUT_FILE)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sections).rstrip() + "\n")
    print(f"Written: {out_path}  ({len(products)} products)")


if __name__ == "__main__":
    main()
