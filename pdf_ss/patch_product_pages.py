#!/usr/bin/env python3
"""
patch_product_pages.py
─────────────────────
Enrich every CM Hammar product page (catalogue/{sku}/index.html) with
structured technical specification attributes sourced from the data sheet
PDF structured data (products.json).

What is updated per page:
  1. <meta name="description"> — richer spec summary for SOLAS-index crawlers
  2. JSON-LD additionalProperty[]  — schema.org Product attributes (machine-readable)
  3. <ul class="meta-description"> — visible spec list on the page

Fields added (if data is available):
  From product page (already present, preserved):
    Approvals, Breaking Strength, Release Depth, Weight

  NEW — from data sheet PDFs (9 fields):
    Activation Depth      ← HYDROSTATIC ACTIVATION DEPTH (SOLAS Red/Yellow label)
    Service Life          ← SERVICE LIFE section
    Operating Temperature ← OPERATING TEMPERATURE section
    Material              ← SPECIFICATIONS table — MATERIAL row
    Colour                ← SPECIFICATIONS table — COLOUR row
    Weight (Components)   ← SPECIFICATIONS table — WEIGHT row (per component)
    Breaking Load         ← SPECIFICATIONS table — BREAKING STRENGHT row
    Weak Link Strength    ← WEAK LINK section
    Approved Standards    ← APPROVED TO STANDARDS section (SOLAS/IMO refs)

Usage:
    python patch_product_pages.py
    python patch_product_pages.py --dry-run   # print changes, do not write
"""

import argparse
import json
import os
import re

SITE_ROOT    = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
PRODUCTS_JSON = os.path.join(os.path.dirname(__file__), "output", "products.json")


# ── Field extraction helpers ──────────────────────────────────────────────────

def _flat(val, sep=" | ") -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, list):
        return sep.join(_flat(v) for v in val if v)
    if isinstance(val, dict):
        if "label" in val and "value" in val:
            return f"{val['label']}: {val['value']}"
        if "variants" in val:
            return sep.join(_flat(v) for v in val["variants"] if v)
        return sep.join(f"{k}: {_flat(v)}" for k, v in val.items() if v and k != "notes")
    return str(val)


def _activation_depth(sections: dict) -> str | None:
    """Return the SOLAS standard activation depth (Red/Yellow label = 1.5-4m)."""
    val = sections.get("HYDROSTATIC ACTIVATION DEPTH")
    if not val:
        return None
    variants = []
    if isinstance(val, list) and val and isinstance(val[0], dict) and "label" in val[0]:
        variants = val
    elif isinstance(val, dict) and "variants" in val:
        variants = val["variants"]
    if variants:
        for v in variants:
            if "yellow" in (v.get("label") or "").lower():
                return v.get("value", "")
        return variants[0].get("value", "")
    return _flat(val) or None


def _spec_table_row(sections: dict, row_key: str) -> str | None:
    """Return a formatted string for one row of the SPECIFICATIONS table."""
    spec = sections.get("SPECIFICATIONS")
    if not isinstance(spec, dict):
        return None
    row = spec.get(row_key)
    if not row:
        return None
    if isinstance(row, dict):
        parts = [f"{comp}: {val}" for comp, val in row.items()
                 if val and val.upper() != "N/A"]
        return " | ".join(parts) or None
    return str(row).strip() or None


def _weak_link(sections: dict) -> str | None:
    val = sections.get("WEAK LINK")
    if not val:
        return None
    text = _flat(val)
    return text.strip() or None


def _approved_standards(sections: dict) -> str | None:
    val = sections.get("APPROVED TO STANDARDS")
    if not val:
        return None
    if isinstance(val, list):
        # Keep first 3 entries to stay concise
        return " | ".join(str(v) for v in val[:3] if v)
    return _flat(val)[:200] or None


def extract_ds_fields(product: dict) -> dict:
    """
    Pull all available technical fields from every structured source on a product:
      1. data_sheet   → primary source (sections table)
      2. user_manual  → key_specs (service_life, temperature_range, etc.)
      3. install guide→ key_fields (voltage, capacity, dimensions, etc.)
      4. certificates → regulations for Approved Standards
      5. product specs→ weight, breaking strength, etc. as fallback
    Returns a dict of {field_name: value_string} with everything found.
    """
    fields = {}

    all_items = (product.get("downloads") or []) + (product.get("approvals") or [])

    # ── 1. Data sheet (richest source) ───────────────────────────────────────
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict) or s.get("document_type") != "data_sheet":
            continue
        sec = s.get("sections") or {}

        v = _activation_depth(sec)
        if v:
            fields.setdefault("Activation Depth", v)

        v = sec.get("SERVICE LIFE")
        if v:
            fields.setdefault("Service Life", _flat(v))

        v = sec.get("OPERATING TEMPERATURE")
        if v:
            fields.setdefault("Operating Temperature", _flat(v))

        v = _spec_table_row(sec, "MATERIAL")
        if v:
            fields.setdefault("Material", v)

        v = _spec_table_row(sec, "COLOUR")
        if v:
            fields.setdefault("Colour", v)

        v = _spec_table_row(sec, "WEIGHT")
        if v:
            fields.setdefault("Weight (Components)", v)

        v = _spec_table_row(sec, "BREAKING STRENGHT")
        if v:
            fields.setdefault("Breaking Load", v)

        v = _weak_link(sec)
        if v:
            fields.setdefault("Weak Link Strength", v)

        v = _approved_standards(sec)
        if v:
            fields.setdefault("Approved Standards", v)

    # ── 2. User manual → key_specs ───────────────────────────────────────────
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict) or s.get("document_type") != "user_manual":
            continue
        ks = s.get("key_specs") or {}
        if isinstance(ks, dict):
            if ks.get("service_life"):
                fields.setdefault("Service Life", str(ks["service_life"]))
            if ks.get("temperature_range"):
                fields.setdefault("Operating Temperature", str(ks["temperature_range"]))
            if ks.get("release_depth"):
                fields.setdefault("Activation Depth", str(ks["release_depth"]))
            if ks.get("breaking_strength"):
                fields.setdefault("Breaking Load", str(ks["breaking_strength"]))
        approvals = s.get("approvals_mentioned") or []
        if approvals:
            fields.setdefault(
                "Approved Standards",
                " | ".join(str(a) for a in approvals[:3]),
            )

    # ── 3. Installation guide / tech info → key_fields ───────────────────────
    GUIDE_TYPES = ("installation_guide", "installation_guide / user_manual",
                   "technical_information", "other")
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict):
            continue
        if s.get("document_type") not in GUIDE_TYPES:
            continue
        kf = s.get("key_fields") or {}
        if not isinstance(kf, dict):
            continue

        # Map common key_field keys to our standard field names
        _mapping = {
            "Temperature range":    "Operating Temperature",
            "temperature_range":    "Operating Temperature",
            "Capacity":             "Capacity",
            "capacity":             "Capacity",
            "Voltage":              "Voltage",
            "voltage":              "Voltage",
            "Battery Type":         "Battery Type",
            "Socket Color":         "Colour",
            "Weight":               "Weight (Components)",
            "Enclosure protection": "Enclosure Protection",
            "Activation angle":     "Activation Angle",
            "External power supply":"Power Supply",
            "Backup-battery":       "Backup Battery",
        }
        for src_key, dst_key in _mapping.items():
            if src_key in kf and kf[src_key]:
                fields.setdefault(dst_key, str(kf[src_key]))

    # ── 4. Certificates → regulations ────────────────────────────────────────
    CERT_TYPES = ("approval_certificate", "approval", "certificate")
    for item in all_items:
        s = item.get("structured") or {}
        if not isinstance(s, dict) or s.get("document_type") not in CERT_TYPES:
            continue
        regs = s.get("regulations") or []
        if regs:
            fields.setdefault(
                "Approved Standards",
                " | ".join(str(r) for r in regs[:2]),
            )
        # Certificate expiry
        if s.get("valid_until"):
            fields.setdefault("Certificate Valid Until", str(s["valid_until"]))
        break   # use first certificate only

    # ── 5. Product page specifications as fallback ────────────────────────────
    page_specs = product.get("specifications") or {}
    if isinstance(page_specs, dict):
        for k, v in page_specs.items():
            if not v:
                continue
            lk = k.lower()
            sv = str(v)
            # Key-name based mapping
            if "breaking" in lk:
                fields.setdefault("Breaking Load", sv)
            elif "weak" in lk:
                fields.setdefault("Weak Link Strength", sv)
            elif "material" in lk:
                fields.setdefault("Material", sv)
            elif "colour" in lk or "color" in lk:
                fields.setdefault("Colour", sv)
            elif "temp" in lk:
                fields.setdefault("Operating Temperature", sv)
            elif "capacity" in lk:
                fields.setdefault("Capacity", sv)
            elif "weight" in lk:
                fields.setdefault("Weight", sv)
            elif "backup" in lk or ("battery" in lk and "type" not in lk):
                fields.setdefault("Backup Battery", sv)
            elif "dimension" in lk or lk == "size":
                fields.setdefault("Dimensions", sv)
            elif lk.startswith("input"):
                fields.setdefault("Inputs", sv)
            elif lk.startswith("output"):
                fields.setdefault("Outputs", sv)
            elif "voltage" in lk:
                fields.setdefault("Voltage", sv)
            # Value-embedded extraction
            kn_m = re.search(r'(\d[\d.,]*\s*kN)', sv, re.I)
            if kn_m and "Breaking Load" not in fields:
                fields["Breaking Load"] = sv
            mat_keywords = ("stainless steel", "polyamid", "polypropylene",
                            "aluminum", "aluminium", "nylon", "plastic", "rubber")
            if "Material" not in fields and any(m in sv.lower() for m in mat_keywords):
                fields["Material"] = sv

    # ── 6. Product notes → service life hint ─────────────────────────────────
    notes = (product.get("notes") or "").strip()
    if notes and "Service Life" not in fields:
        _word_to_num = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "ten": "10",
        }
        years_m = re.search(
            r'(?:replace|service)[^.]*?(\d+|one|two|three|four|five|six|seven|eight|ten)\s*year',
            notes, re.I,
        )
        if years_m:
            raw = years_m.group(1).lower()
            n = _word_to_num.get(raw, raw)
            fields["Service Life"] = f"Replace after {n} years"

    return fields


# ── HTML patching helpers ─────────────────────────────────────────────────────

def _update_meta_description(html: str, sku: str, subtitle: str, fields: dict) -> str:
    """Replace <meta name="description"> with an enriched version."""
    # Build a rich spec summary
    key_fields = ["Activation Depth", "Service Life", "Operating Temperature",
                  "Breaking Load", "Weak Link Strength", "Approved Standards"]
    parts = []
    for f in key_fields:
        if f in fields and fields[f]:
            parts.append(f"{f}: {fields[f]}")

    base = f"{sku} — {subtitle}. SOLAS approved."
    if parts:
        base += " " + " | ".join(parts)
    # Truncate to 320 chars (good SEO length)
    content = base[:320].rstrip(" |")

    new_meta = f'<meta name="description" content="{content}"/>'
    # Replace existing meta description
    html = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*"/>',
        new_meta,
        html,
        count=1,
    )
    return html


def _update_jsonld(html: str, fields: dict) -> str:
    """Add new additionalProperty entries to the schema.org Product JSON-LD."""
    # Find our custom Product JSON-LD block (not the Yoast one)
    pattern = re.compile(
        r'(<script type="application/ld\+json">)\s*(\{.*?"@type":\s*"Product".*?\})\s*(</script>)',
        re.DOTALL,
    )
    m = pattern.search(html)
    if not m:
        return html

    try:
        data = json.loads(m.group(2))
    except json.JSONDecodeError:
        return html

    existing_names = {
        p.get("name", "").lower()
        for p in (data.get("additionalProperty") or [])
    }

    new_props = []
    for name, value in fields.items():
        if name.lower() not in existing_names and value:
            new_props.append({
                "@type": "PropertyValue",
                "name": name,
                "value": value,
            })

    if not new_props:
        return html

    data.setdefault("additionalProperty", []).extend(new_props)

    # Also add SOLAS compliance note to hasCertification if Approved Standards present
    if "Approved Standards" in fields:
        data.setdefault("hasCertification", [])
        solas_cert = {
            "@type": "Certification",
            "name": "SOLAS/IMO Approved",
            "certificationStatus": "https://schema.org/CertificationActive",
            "issuedBy": {"@type": "Organization", "name": "IMO / Class Society"},
        }
        existing_cert_names = {c.get("name", "") for c in data["hasCertification"]}
        if "SOLAS/IMO Approved" not in existing_cert_names:
            data["hasCertification"].append(solas_cert)

    new_block = (
        m.group(1)
        + "\n"
        + json.dumps(data, indent=2, ensure_ascii=False)
        + "\n"
        + m.group(3)
    )
    return html[: m.start()] + new_block + html[m.end() :]


def _update_spec_list(html: str, fields: dict) -> str:
    """Append new <li> items to <ul class="meta-description">."""
    ul_pattern = re.compile(
        r'(<ul\s+class="meta-description">)(.*?)(</ul>)',
        re.DOTALL,
    )
    m = ul_pattern.search(html)
    if not m:
        return html

    existing_html = m.group(2)

    # Determine which fields are already shown
    existing_labels = set(re.findall(r'<strong>([^<]+):</strong>', existing_html, re.I))
    existing_lower = {l.lower() for l in existing_labels}

    new_items = []
    # Fields to show on page (skip redundant ones already shown)
    page_fields = [
        "Activation Depth",
        "Service Life",
        "Operating Temperature",
        "Material",
        "Colour",
        "Weight",
        "Breaking Load",
        "Weak Link Strength",
        "Approved Standards",
        "Backup Battery",
        "Dimensions",
        "Inputs",
        "Outputs",
        "Voltage",
    ]
    for name in page_fields:
        if name.lower() not in existing_lower and name in fields and fields[name]:
            val = fields[name]
            # Trim long values for display
            display_val = val if len(val) <= 120 else val[:117] + "…"
            new_items.append(
                f'\n    <li><strong>{name}:</strong>{display_val}</li>'
            )

    if not new_items:
        return html

    new_ul = m.group(1) + existing_html + "".join(new_items) + "\n  " + m.group(3)
    return html[: m.start()] + new_ul + html[m.end() :]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing files")
    args = parser.parse_args()

    with open(PRODUCTS_JSON, encoding="utf-8") as f:
        products = json.load(f)

    # Build SKU → product lookup
    by_sku = {p["sku"].upper(): p for p in products}

    # Find all catalogue pages
    catalogue_dir = os.path.join(SITE_ROOT, "catalogue")
    page_dirs = [
        d for d in os.listdir(catalogue_dir)
        if os.path.isdir(os.path.join(catalogue_dir, d))
    ]

    updated = 0
    skipped = 0

    for slug in sorted(page_dirs):
        sku = slug.upper()
        html_path = os.path.join(catalogue_dir, slug, "index.html")

        if not os.path.exists(html_path):
            continue

        product = by_sku.get(sku)
        if not product:
            print(f"  [skip] {sku} — not in products.json")
            skipped += 1
            continue

        fields = extract_ds_fields(product)
        if not fields:
            print(f"  [skip] {sku} — no data sheet structured data")
            skipped += 1
            continue

        with open(html_path, encoding="utf-8") as f:
            original = f.read()

        html = original
        subtitle = product.get("subtitle", "")
        html = _update_meta_description(html, sku, subtitle, fields)
        html = _update_jsonld(html, fields)
        html = _update_spec_list(html, fields)

        if html == original:
            print(f"  [no change] {sku}")
            continue

        if args.dry_run:
            print(f"  [would update] {sku} — fields: {list(fields.keys())}")
        else:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  [updated] {sku} — {list(fields.keys())}")
            updated += 1

    print(f"\nDone — {updated} pages updated, {skipped} skipped.")
    if args.dry_run:
        print("(dry run — no files written)")


if __name__ == "__main__":
    main()
