#!/usr/bin/env python3
"""
structure_pdfs.py  —  Use Ollama to turn raw PDF text into structured JSON.

For every document (downloads + approvals) in products.json that has
extracted text, this script sends the text to a local Ollama model and
asks it to return structured fields appropriate for that document type:

  approval_certificate  → cert number, issuing body, valid-until date,
                          approved versions, SOLAS/IMO regulations
  data_sheet            → specifications table, service life, materials,
                          approvals mentioned
  installation_guide    → numbered steps, warnings
  user_manual           → key specs, operational summary, warnings
  generic               → summary + key fields

The same PDF URL is only ever sent to Ollama once regardless of how many
products reference it (shared-PDF cache).  Progress is saved after every
product so a run can be resumed safely.

After all documents are processed the script patches hierarchy.json in-place
so the viewer picks up the structured data immediately on next load.

Usage
-----
    python structure_pdfs.py                       # mistral:latest, all docs
    python structure_pdfs.py --model phi3:mini     # faster, less accurate
    python structure_pdfs.py --limit 20            # only first 20 docs (test)
    python structure_pdfs.py --resume              # skip already-done docs
    python structure_pdfs.py --rebuild-only        # skip Ollama, just repatch hierarchy
"""

import argparse
import json
import logging
import os
import re
import sys
import time

import requests

OUT_DIR    = os.path.join(os.path.dirname(__file__), "output")
JSON_PATH  = os.path.join(OUT_DIR, "products.json")
HIER_PATH  = os.path.join(OUT_DIR, "hierarchy.json")
OLLAMA_URL = "http://localhost:11434"

# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(OUT_DIR, "structure.log"), encoding="utf-8"),
        ],
    )

# --------------------------------------------------------------------------
# Ollama
# --------------------------------------------------------------------------

def check_ollama(preferred_model: str) -> str:
    """Verify Ollama is running; return the model name to use."""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        logging.info(f"Ollama running — models: {', '.join(models)}")
    except Exception as e:
        logging.error(f"Ollama not reachable at {OLLAMA_URL}: {e}")
        logging.error("Start it with:  ollama serve")
        sys.exit(1)

    # Accept partial match (e.g. "mistral" matches "mistral:latest")
    for m in models:
        if preferred_model in m or m in preferred_model:
            return m
    logging.warning(f"Model '{preferred_model}' not found. Available: {', '.join(models)}")
    logging.warning(f"Run:  ollama pull {preferred_model}")
    logging.info(f"Falling back to first available model: {models[0]}")
    return models[0]


def call_ollama(model: str, prompt: str) -> dict | None:
    """POST to Ollama generate endpoint, parse JSON from response."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.05, "num_predict": 512},
            },
            timeout=300,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        return json.loads(m.group() if m else raw)
    except Exception as e:
        logging.warning(f"  Ollama call failed: {e}")
        return None


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_RATE_LIMITED = "__rate_limited__"  # sentinel: retry on next run

def call_groq(api_key: str, model: str, prompt: str) -> dict | None | str:
    """POST to Groq chat completions endpoint.  Returns dict on success,
    GROQ_RATE_LIMITED sentinel on 429 (caller should not cache this),
    or None on other errors."""
    for attempt in range(4):
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.05,
                    "max_tokens": 768,
                },
                timeout=30,
            )
            if resp.status_code == 429:
                wait = int(resp.headers.get("retry-after", 30))
                logging.info(f"  Rate limited — waiting {wait}s (attempt {attempt+1}/4)")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            raw = resp.json()["choices"][0]["message"]["content"].strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            return json.loads(m.group() if m else raw)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 429:
                wait = int(e.response.headers.get("retry-after", 30))
                logging.info(f"  Rate limited — waiting {wait}s (attempt {attempt+1}/4)")
                time.sleep(wait)
                continue
            logging.warning(f"  Groq call failed: {e}")
            return None
        except Exception as e:
            logging.warning(f"  Groq call failed: {e}")
            return None
    logging.warning("  Groq: max retries exceeded — will retry on next run")
    return GROQ_RATE_LIMITED

# --------------------------------------------------------------------------
# Document type detection
# --------------------------------------------------------------------------

def detect_type(name: str, text: str) -> str:
    n = name.lower()
    t = text.lower()
    if any(k in n for k in ["module b", "type approval", "type-approval", "certificate", "certif",
                              "mca redens", "bureau veritas", "ec/uscg", "uk type", "bv "]):
        return "approval"
    if any(k in t for k in ["certificatenumber:", "certificate number:", "type-examination certificate",
                              "type examination certificate", "this certificate is issued to",
                              "thiscertificateisissuedto"]):
        return "approval"
    if any(k in n for k in ["data sheet", "product data", "technical data"]):
        return "data_sheet"
    if any(k in n for k in ["installation", "guidance"]):
        return "installation"
    if any(k in n for k in ["user manual", " manual"]):
        return "manual"
    return "generic"

# --------------------------------------------------------------------------
# Prompts — each returns the prompt string for that document type
# --------------------------------------------------------------------------

_APPROVAL_FIELDS = {
    "document_type":      "always the string \"approval_certificate\"",
    "certificate_number": "the official cert number, e.g. \"73672/B0 UK\" or \"07493/G0\"",
    "issuing_body":       "e.g. \"Bureau Veritas\", \"MCA\", \"Lloyd's Register\"",
    "certificate_type":   "e.g. \"UK Type Examination Module B\", \"EC Type Examination\", \"Type Approval\"",
    "product_name":       "full product name",
    "product_designation":"short technical designation, e.g. \"H20R, Release Depth 1.5-4m\"",
    "approved_versions":  "array of approved variant strings",
    "valid_until":        "ISO date string \"YYYY-MM-DD\" or null",
    "regulations":        "array of standard/regulation strings referenced (SOLAS, IMO Res., EU Directive, etc.)",
    "manufacturer":       "company name",
    "notes":              "any limitations or important conditions, or null",
}

_DATA_SHEET_FIELDS = {
    "document_type":        "always the string \"data_sheet\"",
    "product_name":         "full product name from the document title",
    "hs_code":              "HS code string if present, else null",
    "country_of_origin":    "country of origin if present, else null",
    "sections": (
        "array of objects — one per section heading found in the document, IN DOCUMENT ORDER. "
        "Each object: {\"heading\": \"EXACT HEADING AS WRITTEN IN THE PDF (e.g. HYDROSTATIC ACTIVATION DEPTH, WEAK LINK, SERVICE LIFE, APPROVED TO STANDARDS, LABEL AND PRODUCT MARKING, DUAL ASSEMBLY, TRANSPORT AND STORAGE, PACKING SPECIFICATIONS)\", "
        "\"content\": \"complete text of that section. Use \\n to separate distinct items or label variants. Copy ALL values exactly.\"}. "
        "Include EVERY section that has a heading — do not merge or skip any."
    ),
    "specifications_table": (
        "object with ALL rows from any tabular specifications section. "
        "Key = row label (flatten multi-column tables: e.g. 'weight_housing', 'size_rope_sling', 'colour_cable'). "
        "Value = string with the value. Omit N/A cells."
    ),
    "warnings":             "array of safety warning strings found in the document (e.g. 'Do not paint', 'Do not power wash', 'Discard if dropped')",
}

_INSTALL_FIELDS = {
    "document_type": "always the string \"installation_guide\"",
    "product_name":  "product this guide is for",
    "steps":         "array of strings — numbered installation steps in order",
    "warnings":      "array of strings — safety warnings and prohibitions (e.g. 'Do not paint')",
    "notes":         "any other important notes, or null",
}

_MANUAL_FIELDS = {
    "document_type":  "always the string \"user_manual\"",
    "product_name":   "product name",
    "how_it_works":   "1-2 sentence description of how the product operates",
    "key_specs": {
        "release_depth":     "string or null",
        "breaking_strength": "string or null",
        "service_life":      "string or null",
        "temperature_range": "string or null",
    },
    "approvals_mentioned": "array of approval/certification strings mentioned",
    "warnings":            "array of safety warnings and prohibitions",
}

_GENERIC_FIELDS = {
    "document_type": "best guess: data_sheet / installation_guide / user_manual / certificate / other",
    "product_name":  "product name or null",
    "summary":       "2-3 sentence summary of the document content",
    "key_fields":    "object of any important key-value pairs from the document",
}

_NOTE = (
    "NOTE: The raw text may have words run together (PDF extraction artifact) — "
    "reconstruct the correct words when you find them (e.g. 'CertificateNumber' → 'Certificate Number')."
)

def sanitize(text: str) -> str:
    """Remove control characters that can break JSON payloads."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)


# --------------------------------------------------------------------------
# Regex data sheet extractor — no LLM needed
# --------------------------------------------------------------------------

# Exact known section headings found in CM Hammar product data sheets.
# Sorted longest-first so that e.g. "MANUAL ACTIVATION" is checked before "ACTIVATION".
_DS_HEADERS = sorted([
    'HYDROSTATIC ACTIVATION DEPTH',
    'AUTOMATIC ACTIVATION',
    'MANUAL ACTIVATION',
    'WEAK LINK',
    'OPERATING TEMPERATURE',
    'SERVICE LIFE',
    'APPROVED TO STANDARDS',
    'LABEL AND PRODUCT MARKING',
    'DUAL ASSEMBLY',
    'TRANSPORT AND STORAGE',
    'PACKING SPECIFICATIONS',
    'DESCRIPTION',
    'SPECIFICATIONS',
    'INSTALLATION',
    'MAINTENANCE',
], key=len, reverse=True)

_HEADER_RE = re.compile(
    r'^(' + '|'.join(re.escape(h) for h in _DS_HEADERS) + r')',
    re.MULTILINE,
)

# Colour-label pattern used by HYDROSTATIC ACTIVATION DEPTH
_LABEL_RE = re.compile(
    r'^((?:Red|Yellow|Green|Blue|White)(?:[/\w\s]+)?(?:Top\s+)?Label)\s*[:\-]\s*(.+)$',
    re.IGNORECASE,
)


# Lines that are clearly PDF artifacts (footers, garbled interleaved text, noise)
_NOISE_RE = re.compile(
    r'^(?:'
    r'\+\d[\d\s]{6,}'           # phone numbers
    r'|[\w.]+@[\w.]+\.\w+'      # email addresses
    r'|\d{4}$'                   # bare year
    r'|\d{3,6}\s'               # lines starting with digits+space (page nums like "4202 the LSA")
    r'|\d+\.[a-z]\w*[A-Z]'     # garbled version refs (e.g. "2.reV")
    r'|[A-Z]\.\w{2,5}[A-Z]'    # garbled interleaved (like "2.reV")
    r'|(?:[a-z]{1,4}[A-Z]){2,}' # camelCase garble like "aerl eHc2tr0ic"
    r'|CM\s+Hammar'             # footer: company name
    r'|www\.'                   # footer: website URL
    r'|SE-\d{3}'                # footer: Swedish postal code
    r'|August\s+Barks'          # footer: street name
    r')'
)

def _is_garbled(line: str) -> bool:
    """True if a line looks like garbled text from multi-column PDF extraction."""
    if _NOISE_RE.search(line):
        return True
    # Garbled lines often have consecutive CONSONANT+lowercase char clusters
    # like 'IfT', 'afnrodm', 'oSthyestre' — detect by ratio of transitions
    stripped = re.sub(r'[^A-Za-z]', '', line)
    if len(stripped) < 6:
        return False
    # Count unusual uppercase-then-lowercase inside a word (not at word start)
    garble_chars = len(re.findall(r'(?<=[a-z])[A-Z](?=[a-z])', line))
    if garble_chars >= 3:
        return True
    return False


def _parse_section(heading: str, content: str):
    """Convert a section's raw text into the best Python structure."""
    lines = [
        l.strip() for l in content.splitlines()
        if l.strip() and len(l.strip()) > 1 and not _is_garbled(l.strip())
    ]
    if not lines:
        return None

    # HYDROSTATIC / MANUAL ACTIVATION → list of {label, value} colour variants
    if re.search(r'hydrostatic|activation depth|manual activation', heading, re.I):
        variants, general = [], []
        last_was_variant = False
        for line in lines:
            m = _LABEL_RE.match(line)
            if m:
                variants.append({"label": m.group(1).strip(), "value": m.group(2).strip()})
                last_was_variant = True
            elif last_was_variant and line and line[0].islower():
                # Lowercase continuation of the previous label line
                variants[-1]["value"] += " " + line
            else:
                # Uppercase non-label line ends continuation mode
                if line and line[0].isupper():
                    last_was_variant = False
                general.append(line)
        if not variants:
            return lines
        if not general:
            return variants  # clean flat array
        return {"variants": variants, "notes": general}

    # APPROVED TO STANDARDS → filtered list of standards references
    if re.search(r'approved|standards?', heading, re.I):
        # Keep only lines that look like real standards references
        standards = []
        for line in lines:
            # Skip lines that start with digits (garbled page numbers like "4202 the LSA Code")
            if line and line[0].isdigit():
                continue
            # Accept: IMO/SOLAS refs, Chapter references, EU Directives, footnotes
            if re.search(
                r'IMO|SOLAS|Chapter|ISO|IEC|EU\s+Dir|directive|LSA\s+Code|Marine\s+Equip|^\*|MSC|MED\b|96/98',
                line, re.I
            ):
                standards.append(line)
        return standards if standards else [l for l in lines if len(l) > 5 and not line[0].isdigit()]

    # SERVICE LIFE → join continuation lines into one sentence
    if re.search(r'service.life', heading, re.I):
        return ' '.join(lines) if lines else None

    # OPERATING TEMPERATURE → single value or list
    if re.search(r'operating.temp|temperature', heading, re.I):
        return lines[0] if len(lines) == 1 else lines

    # PACKING SPECIFICATIONS → keep non-warning lines as content; warnings go separately
    if re.search(r'packing|specification', heading, re.I):
        content_lines = [l for l in lines if not l.startswith(('•', 'Do not', 'If an'))]
        if content_lines:
            return content_lines[0] if len(content_lines) == 1 else content_lines
        return lines[0] if lines else None

    # General: try key-value pairs (colon separator)
    kv, plain = {}, []
    for line in lines:
        m = re.match(r'^([^:]{2,60})\s*:\s*(.+)$', line)
        if m:
            kv[m.group(1).strip()] = m.group(2).strip()
        else:
            plain.append(line)

    if kv and not plain:
        return kv
    if kv and plain:
        kv["notes"] = plain
        return kv
    return plain[0] if len(plain) == 1 else plain


def _dedouble(raw: str) -> str:
    """De-interleave doubled PDF text (e.g. 'HHSS CCOODDEE' → 'HS CODE').
    Strips spaces, then takes every other character starting at index 0."""
    s = raw.replace(' ', '')
    return s[::2]


def extract_specs_table_from_pdf(pdf_path: str) -> dict | None:
    """
    Use pdfplumber table extraction to parse the SPECIFICATIONS table
    from a CM Hammar data sheet PDF.

    Returns a nested dict:  {row_label: {column_header: value}}
    e.g. {"SIZE": {"H20 HOUSING": "L:96 mm, w: 64 mm, H: 62 mm", "ROPE SLING": "Diameter; 8 mm"}, ...}
    Returns None if no table is found or the file cannot be opened.
    """
    import pdfplumber
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue
                    first_cell = str(table[0][0] or '').strip() if table[0] else ''
                    if not first_cell.startswith('SPECIFICATIONS'):
                        continue
                    # Valid SPECIFICATIONS table — parse it
                    headers = [str(h or '').strip() for h in table[0][1:]]
                    headers = [h for h in headers if h]
                    if not headers:
                        continue
                    result = {}
                    for row in table[1:]:
                        if not row or not row[0]:
                            continue
                        # Strip trailing drawing reference numbers (e.g. "COLOUR\n6")
                        prop = re.sub(r'\s*\n?\d+\s*$', '', str(row[0])).strip()
                        if not prop or _is_garbled(prop):
                            continue
                        for i, header in enumerate(headers):
                            val_idx = i + 1
                            if val_idx >= len(row) or row[val_idx] is None:
                                continue
                            val = re.sub(r'\n?\d+\s*$', '', str(row[val_idx])).strip()
                            if val and val.upper() != 'N/A':
                                result.setdefault(prop, {})[header] = val
                    if result:
                        return result
    except Exception as exc:
        logging.warning(f"specs table extraction failed for {pdf_path}: {exc}")
    return None


def extract_datasheet(name: str, text: str) -> dict:
    """
    Parse a CM Hammar product data sheet using known section headings.
    Returns a structured dict without calling any LLM.
    """
    clean = sanitize(text)

    # Find all known section headings in document order
    matches = list(_HEADER_RE.finditer(clean))
    sections = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        # Content runs from the match end to the start of the next heading
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(clean)
        raw = clean[start:end]
        # Skip any text on the same line as the heading (e.g. "* SOLAS 74 Convention")
        # by finding the first newline in the unstripped raw content.
        first_nl = raw.find('\n')
        content = raw[first_nl:].strip() if first_nl != -1 else raw.strip()
        if heading in sections:
            # Duplicate heading (two-column PDF): append rather than overwrite
            existing = sections[heading]
            parsed = _parse_section(heading, content)
            if parsed:
                if isinstance(existing, list) and isinstance(parsed, list):
                    existing.extend(x for x in parsed if x not in existing)
                elif isinstance(existing, dict) and isinstance(parsed, dict):
                    existing.update(parsed)
            continue
        parsed = _parse_section(heading, content)
        if parsed is not None:
            sections[heading] = parsed

    # Safety/warning sentences
    warnings = re.findall(
        r'(?:•\s*|^\s*[-*]\s*)(Do not[^\n•*]{5,80}|If an? [^\n•*]{5,80}(?:shall|should) be [^\n•*]{5,60})',
        clean, re.MULTILINE | re.I,
    )
    warnings = [w.strip().rstrip('.') for w in warnings if len(w.strip()) > 8]

    # HS code — try clean form first, then de-doubled garbled form
    hs_code = None
    hs_m = re.search(r'HS\s*CODE\s+([\d]{6,})', clean, re.I)
    if hs_m:
        hs_code = hs_m.group(1)
    else:
        # Garbled doubled form in PDF header: "HHSS C COODDEE 8 844779988999977"
        # Anchor on "H+S+" and find the nearby digit cluster
        hs_g = re.search(r'H+S+[^0-9]{1,25}([\d][\d\s]{10,30})(?=,)', clean, re.I)
        if hs_g:
            raw_digits = hs_g.group(1).replace(' ', '')
            candidate = raw_digits[::2]
            if re.match(r'^\d{6,12}$', candidate):
                hs_code = candidate

    # Country of origin — try clean form first, then de-doubled garbled form
    country = None
    co_m = re.search(r'Country\s+of\s+Origin\s+([A-Z][A-Za-z]+)', clean)
    if co_m:
        country = co_m.group(1)
    else:
        # Garbled doubled form: find the HS code line and extract the last ALL-CAPS word block
        # which is the doubled country name (e.g. "S SWWEEDDEENN" → de-doubled → "SWEDEN")
        hs_line_m = re.search(
            r'H+S+[^0-9]{1,25}[\d][\d\s]{10,30},\s*,?\s*(.+?)(?=\n)',
            clean, re.I
        )
        if hs_line_m:
            last_caps = re.search(r'([A-Z][A-Z\s]+)$', hs_line_m.group(1))
            if last_caps:
                raw_co = last_caps.group(1).strip().replace(' ', '')
                candidate = raw_co[::2]
                if re.match(r'^[A-Z]{3,}$', candidate):
                    country = candidate

    return {
        "document_type":     "data_sheet",
        "product_name":      name,
        "hs_code":           hs_code,
        "country_of_origin": country,
        "sections":          sections,
        "warnings":          warnings,
    }


def make_prompt(doc_type: str, name: str, text: str) -> str:
    schema_map = {
        "approval":     _APPROVAL_FIELDS,
        "data_sheet":   _DATA_SHEET_FIELDS,
        "installation": _INSTALL_FIELDS,
        "manual":       _MANUAL_FIELDS,
        "generic":      _GENERIC_FIELDS,
    }
    schema = json.dumps(schema_map.get(doc_type, _GENERIC_FIELDS), indent=2)
    return (
        f"You are a maritime equipment documentation analyst.\n"
        f"Extract structured information from the following {doc_type.replace('_', ' ')} document.\n"
        f"{_NOTE}\n\n"
        f"Document name: {name}\n\n"
        f"Return ONLY a valid JSON object with exactly these fields:\n{schema}\n\n"
        f"Document text (may be truncated):\n\"\"\"\n{sanitize(text[:4500])}\n\"\"\"\n\n"
        f"Return only the JSON object, no explanation, no markdown."
    )

# --------------------------------------------------------------------------
# Hierarchy rebuild
# --------------------------------------------------------------------------

def rebuild_hierarchy(products: list):
    """Patch hierarchy.json in-place: replace every embedded product record
    with the updated version from products (matched by SKU)."""
    if not os.path.exists(HIER_PATH):
        logging.warning("hierarchy.json not found — skipping rebuild")
        return

    with open(HIER_PATH, encoding="utf-8") as f:
        tree = json.load(f)

    index = {p["sku"]: p for p in products}

    def walk(node):
        node["products"] = [index.get(p["sku"], p) for p in node.get("products", [])]
        for child in node.get("children", {}).values():
            walk(child)

    walk(tree)

    with open(HIER_PATH, "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    logging.info("hierarchy.json rebuilt with structured data")

# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model",        default=None,              help="Model name (default depends on provider)")
    parser.add_argument("--provider",     default="ollama",          help="ollama or groq")
    parser.add_argument("--groq-key",     default=None,              help="Groq API key (or set GROQ_API_KEY env var)")
    parser.add_argument("--limit",        type=int, default=None,    help="Process at most N documents")
    parser.add_argument("--resume",       action="store_true",       help="Skip docs with structured data (non-null)")
    parser.add_argument("--retry-failed", action="store_true",       help="Also retry docs where structured=null")
    parser.add_argument("--rebuild-only", action="store_true",       help="Skip LLM, just rebuild hierarchy.json")
    parser.add_argument("--retype",       default=None,              help="Re-process only this doc type (e.g. data_sheet) — keeps all other structured data")
    parser.add_argument("--fix-specs",    action="store_true",       help="Re-extract SPECIFICATIONS table from PDFs and patch structured data, then rebuild hierarchy")
    args = parser.parse_args()

    setup_logging()
    os.makedirs(OUT_DIR, exist_ok=True)

    with open(JSON_PATH, encoding="utf-8") as f:
        products = json.load(f)

    if args.rebuild_only:
        rebuild_hierarchy(products)
        return

    if args.fix_specs:
        updated = 0
        for product in products:
            for item in (product.get("downloads") or []):
                s = item.get("structured") or {}
                if not isinstance(s, dict) or s.get("document_type") != "data_sheet":
                    continue
                local = item.get("local_path", "")
                if not local:
                    continue
                pdf_path = os.path.join(OUT_DIR, local.replace("\\", os.sep).replace("/", os.sep))
                if not os.path.exists(pdf_path):
                    logging.warning(f"PDF not found: {pdf_path}")
                    continue
                table = extract_specs_table_from_pdf(pdf_path)
                if table:
                    s.setdefault("sections", {})["SPECIFICATIONS"] = table
                    logging.info(f"  {product['sku']}: specs table -> {list(table.keys())}")
                    updated += 1
        logging.info(f"Updated SPECIFICATIONS for {updated} data sheets")
        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        rebuild_hierarchy(products)
        return

    # Resolve provider and model
    groq_key = None
    if args.provider == "groq":
        groq_key = args.groq_key or os.environ.get("GROQ_API_KEY")
        if not groq_key:
            logging.error("Groq API key required: pass --groq-key or set GROQ_API_KEY")
            sys.exit(1)
        model = args.model or "llama-3.1-8b-instant"
        logging.info(f"Provider: Groq  model: {model}")
    else:
        model = check_ollama(args.model or "phi3:mini")

    # Pre-populate shared cache from already-structured docs (for --resume)
    url_cache: dict = {}
    def should_skip(item):
        # --retype: only re-process items that match the specified doc type
        if args.retype:
            this_type = detect_type(item["name"], item.get("text", ""))
            if this_type != args.retype:
                return True  # preserve structured data for other types
            return False  # always re-process the target type
        if not args.resume:
            return False
        if "structured" not in item:
            return False
        # Skip successes always; skip failures unless --retry-failed
        return item["structured"] is not None or not args.retry_failed

    if args.resume:
        for p in products:
            for section in ("downloads", "approvals"):
                for item in p.get(section, []):
                    if "structured" in item and item["structured"] is not None and item["url"] not in url_cache:
                        url_cache[item["url"]] = item["structured"]

    # Count work
    total = sum(
        1 for p in products
        for section in ("downloads", "approvals")
        for item in p.get(section, [])
        if item.get("text") and not should_skip(item)
    )
    logging.info(f"Documents to process: {total}  (model: {model})")

    processed = 0

    for product in products:
        changed = False
        for section in ("downloads", "approvals"):
            for item in product.get(section, []):
                if not item.get("text"):
                    continue
                if should_skip(item):
                    continue
                if args.limit is not None and processed >= args.limit:
                    continue

                url = item["url"]

                # Shared PDF cache — same file across multiple products
                if url in url_cache:
                    item["structured"] = url_cache[url]
                    logging.info(f"[cache] {item['name'][:70]}")
                    changed = True
                    continue

                doc_type = detect_type(item["name"], item["text"])
                logging.info(f"[{processed+1}/{total}] {doc_type.upper()}: {item['name'][:65]}")

                # Data sheets: regex extraction — no LLM call needed
                if doc_type == "data_sheet":
                    result = extract_datasheet(item["name"], item["text"])
                    logging.info(f"  → regex: {list(result['sections'].keys())[:5]}")
                elif groq_key:
                    prompt = make_prompt(doc_type, item["name"], item["text"])
                    result = call_groq(groq_key, model, prompt)
                else:
                    prompt = make_prompt(doc_type, item["name"], item["text"])
                    result = call_ollama(model, prompt)

                if result and result != GROQ_RATE_LIMITED:
                    item["structured"] = result
                    url_cache[url] = result
                    logging.info(f"  → {list(result.keys())}")
                elif result == GROQ_RATE_LIMITED:
                    # Don't set item["structured"] or cache — will retry on next --resume
                    logging.warning("  → Rate limited after retries — will retry next run")
                else:
                    item["structured"] = None
                    url_cache[url] = None
                    logging.warning("  → Structuring failed — stored null")

                processed += 1
                # Data sheets use regex (no LLM); other types call Groq → respect TPM limit
                time.sleep(0.1 if doc_type == "data_sheet" or not groq_key else 5)

                # Save after every item so progress isn't lost if killed mid-product
                with open(JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(products, f, ensure_ascii=False, indent=2)

    logging.info(f"Done — {processed} documents processed")

    # Rebuild hierarchy.json so viewer picks up the new structured fields
    rebuild_hierarchy(products)
    logging.info("All done. Reload hierarchy.json in the viewer to see structured data.")


if __name__ == "__main__":
    main()
