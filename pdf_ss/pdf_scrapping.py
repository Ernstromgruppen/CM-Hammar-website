#!/usr/bin/env python3
"""
Scraper for https://www.cmhammar.com/catalogue/

What it does
------------
1. Crawls every "product-category" archive page (and their pagination) to
   discover the URL of every individual product page under /catalogue/<sku>/.
2. Visits every product page and extracts:
       - sku / title / subtitle
       - main image
       - categories, tags
       - the "Description" spec block (Approvals, Product Specification,
         Breaking Strength, Release Depth, Weight, Notes, ... - whatever
         labels exist, captured generically as key/value pairs)
       - free-text notes
       - "Downloads" PDFs (name + url)
       - "Approvals" PDFs (name + url)
       - "Related products" (sku + url)
3. Downloads every PDF referenced on a product page, extracts its text with
   pdfplumber (falls back to PyPDF2 if pdfplumber fails), and stores that
   text directly inside the product's JSON record next to the PDF link.
4. Writes one consolidated JSON file with all products, plus keeps the raw
   PDFs on disk (in case you want the originals too).

Usage
-----
    python scrape_cmhammar.py                     # full run
    python scrape_cmhammar.py --limit 10           # only first 10 products (test run)
    python scrape_cmhammar.py --skip-pdf-text       # don't download/parse PDFs (faster)
    python scrape_cmhammar.py --resume              # skip products already in output json

Output
------
    output/products.json        <- final structured data
    output/pdfs/<sku>/<file>.pdf <- downloaded PDFs
    output/log.txt              <- run log / errors
"""

import argparse
import json
import logging
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

BASE = "https://www.cmhammar.com"
CATALOGUE_URL = f"{BASE}/catalogue/"

# Top level category roots taken from the Catalogue page. Each of these
# has sub-categories, and each sub-category is paginated. We crawl all of
# it recursively by just following every "product-category" link we find
# and every pagination link, then collecting every "/catalogue/<slug>/"
# link we encounter along the way.
CATEGORY_SEEDS = [
    f"{BASE}/product-category/h20/",
    f"{BASE}/product-category/remote-release-systems/",
    f"{BASE}/product-category/lifejacket-inflators/",
    f"{BASE}/product-category/ex/",
    f"{BASE}/product-category/polar-box/",
    f"{BASE}/product-category/manual-release-products/",
]

OUT_DIR = "output"
PDF_DIR = os.path.join(OUT_DIR, "pdfs")
JSON_PATH = os.path.join(OUT_DIR, "products.json")
LOG_PATH = os.path.join(OUT_DIR, "log.txt")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CatalogueResearchBot/1.0; +https://example.com)"
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

REQUEST_DELAY = 0.6  # seconds between requests, be polite
TIMEOUT = 30


def setup_logging():
    os.makedirs(OUT_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def get(url, **kwargs):
    """GET with simple retry."""
    for attempt in range(3):
        try:
            resp = SESSION.get(url, timeout=TIMEOUT, **kwargs)
            resp.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return resp
        except requests.RequestException as e:
            logging.warning(f"GET failed ({attempt+1}/3) {url}: {e}")
            time.sleep(2 * (attempt + 1))
    logging.error(f"GET permanently failed: {url}")
    return None


# --------------------------------------------------------------------------
# Step 1: discover all product URLs
# --------------------------------------------------------------------------

def category_slug_path(cat_url):
    """e.g. https://.../product-category/h20/h20-all-products/ -> ('h20', 'h20-all-products')"""
    path = urlparse(cat_url).path.strip("/")
    parts = path.split("/")
    # parts[0] == 'product-category'
    parts = parts[1:]
    return tuple(parts) if parts else tuple()


def discover_product_urls():
    """Crawl category archive pages (+ their sub-categories + pagination)
    and collect every distinct /catalogue/<slug>/ product URL, while
    recording the category/sub-category page(s) each product was found
    listed under. This membership map -- not text guessed off the product
    page -- is what we use to place each product (and therefore its PDFs)
    correctly in the output hierarchy, since the real nav is the ground
    truth and a product can legitimately be listed under more than one
    sub-category.

    Returns:
        product_urls: sorted list of all discovered product URLs
        membership: { product_url: set of category_url it was listed under }
        category_titles: { category_url: human title }
    """
    to_visit = list(CATEGORY_SEEDS)
    visited_categories = set()
    product_urls = set()
    membership = {}
    category_titles = {}

    while to_visit:
        cat_url = to_visit.pop()
        cat_url = cat_url.split("#")[0]
        if cat_url in visited_categories:
            continue
        visited_categories.add(cat_url)

        resp = get(cat_url)
        if resp is None:
            continue
        soup = BeautifulSoup(resp.text, "lxml")
        logging.info(f"Scanning category page: {cat_url}")

        h1 = soup.find("h1")
        if h1:
            category_titles[cat_url] = h1.get_text(strip=True)

        for a in soup.find_all("a", href=True):
            href = urljoin(BASE, a["href"])
            parsed = urlparse(href)
            path = parsed.path

            # sub-category link -> needs to be crawled too
            if "/product-category/" in path and href not in visited_categories:
                to_visit.append(href)

            # pagination link on a category/listing page, e.g. ?page=2
            if "/product-category/" in path and "page=" in (parsed.query or ""):
                if href not in visited_categories:
                    to_visit.append(href)

            # an actual product page
            if re.match(r"^/catalogue/[^/]+/?$", path) and path.rstrip("/") != "/catalogue":
                product_url = href.rstrip("/") + "/"
                product_urls.add(product_url)
                # strip pagination query off the category url before recording
                # membership, so page 1 / page 2 / page 3 of the same
                # sub-category all collapse to one membership entry
                clean_cat_url = cat_url.split("?")[0]
                membership.setdefault(product_url, set()).add(clean_cat_url)

    logging.info(f"Discovered {len(product_urls)} unique product URLs across {len(visited_categories)} category pages")
    return sorted(product_urls), membership, category_titles


# --------------------------------------------------------------------------
# Step 2: parse a single product page
# --------------------------------------------------------------------------

def parse_links_section(soup, heading_text):
    """Given the page soup, find a <h3>/<h2>/heading whose text matches
    heading_text (e.g. 'Downloads', 'Approvals') and return the list of
    (name, url) links that follow it, up until the next heading."""
    results = []
    heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if tag.get_text(strip=True).lower() == heading_text.lower():
            heading = tag
            break
    if not heading:
        return results

    # Walk forward through siblings until we hit another heading of the
    # same level (or run out), collecting <a> tags as we go.
    for sib in heading.find_all_next():
        if sib.name in ("h2", "h3", "h4"):
            break
        if sib.name == "a" and sib.get("href"):
            name = sib.get_text(strip=True) or sib["href"]
            url = urljoin(BASE, sib["href"])
            results.append({"name": name, "url": url})
    return results


def parse_description_block(soup):
    """Extract the labelled spec fields under 'Description', e.g.
    'Approvals: EC approved', 'Release Depth: 1,5-4 m', plus the free
    text 'Notes' paragraph(s)."""
    specs = {}
    notes = ""

    desc_heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if tag.get_text(strip=True).lower() == "description":
            desc_heading = tag
            break
    if not desc_heading:
        return specs, notes

    seen_notes_label = False
    node = desc_heading
    while True:
        node = node.find_next()
        if node is None:
            break
        if node.name in ("h2", "h3", "h4"):
            break
        if node.name == "li":
            strong = node.find(["strong", "b"])
            if strong:
                label = strong.get_text(strip=True).rstrip(":")
                value = node.get_text(strip=True)
                value = value[len(strong.get_text(strip=True)):].lstrip(": ").strip()
                if label.lower() == "notes":
                    seen_notes_label = True
                    if value:
                        notes += value + "\n"
                else:
                    specs[label] = value
        elif node.name == "strong" and not node.find_parent("li"):
            # Bug fix: Notes is sometimes a bare <strong>Notes:</strong>
            # outside any <li>, e.g. after the spec <ul> on CM Hammar pages.
            label = node.get_text(strip=True).rstrip(":")
            if label.lower() == "notes":
                seen_notes_label = True
        elif node.name == "p" and seen_notes_label:
            txt = node.get_text(strip=True)
            if txt:
                notes += txt + "\n"

    return specs, notes.strip()


def parse_related_products(soup):
    related = []
    heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if tag.get_text(strip=True).lower() == "related products":
            heading = tag
            break
    if not heading:
        return related
    for a in heading.find_all_next("a", href=True):
        href = a["href"]
        if re.search(r"/catalogue/[^/]+/?$", href):
            sku_text = a.get_text(strip=True)
            related.append({"label": sku_text, "url": urljoin(BASE, href)})
    return related


import hashlib

# Cache so the same PDF (e.g. a manual linked from 30 different products)
# is only ever downloaded and text-extracted once, no matter how many
# products reference it. Keyed by the PDF's URL.
_PDF_CACHE = {}


def download_and_extract_pdf(url, want_text=True):
    """Download a PDF once (cached across the whole run, since many
    products link the exact same manual/approval cert) and extract its
    text. Returns dict {local_path, text}."""
    if url in _PDF_CACHE:
        return _PDF_CACHE[url]

    # Bug fix: store PDFs in a flat shared cache dir (not per-SKU) since the
    # same PDF (e.g. H20 manual) is linked from many products. The JSON
    # records the path; callers can build per-product views from the JSON.
    url_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    filename = os.path.basename(urlparse(url).path) or "file.pdf"
    safe_name = f"{url_hash}_{filename}"
    shared_dir = os.path.join(PDF_DIR, "_shared")
    local_path = os.path.join(shared_dir, safe_name)
    rel_path = os.path.relpath(local_path, OUT_DIR)
    os.makedirs(PDF_DIR, exist_ok=True)

    os.makedirs(shared_dir, exist_ok=True)
    if not os.path.exists(local_path):
        resp = get(url)
        if resp is None:
            result = {"local_path": None, "text": None}
            _PDF_CACHE[url] = result
            return result
        with open(local_path, "wb") as f:
            f.write(resp.content)

    text = extract_pdf_text(local_path) if want_text else None
    result = {"local_path": rel_path, "text": text}
    _PDF_CACHE[url] = result
    return result


def _words_to_text(words):
    """Convert pdfplumber word dicts (with bounding boxes) to a text string."""
    if not words:
        return ""
    words_s = sorted(words, key=lambda w: (round(w["top"] / 3) * 3, w["x0"]))
    lines, cur = [], [words_s[0]]
    for w in words_s[1:]:
        if abs(w["top"] - cur[-1]["top"]) < 5:
            cur.append(w)
        else:
            lines.append(" ".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
            cur = [w]
    lines.append(" ".join(x["text"] for x in sorted(cur, key=lambda x: x["x0"])))
    return "\n".join(lines)


def _extract_page_text(page):
    """Extract text from one pdfplumber page, handling two-column PDF layouts.

    CM Hammar data sheets use a two-column layout. pdfplumber's default
    extract_text() reads characters left-to-right across the page width and
    interleaves both columns into garbled output. We split words at the page
    midpoint and reconstruct each column independently, then concatenate them.
    """
    try:
        words = page.extract_words(x_tolerance=3, y_tolerance=3)
    except Exception:
        return page.extract_text() or ""

    if not words:
        return page.extract_text() or ""

    mid = page.width / 2
    left_words = [w for w in words if w["x1"] <= mid + 5]
    right_words = [w for w in words if w["x0"] >= mid - 5]

    # Only use column split when both halves have meaningful content
    if len(left_words) >= 10 and len(right_words) >= 10:
        left_text = _words_to_text(left_words)
        right_text = _words_to_text(right_words)
        if left_text.strip() and right_text.strip():
            return left_text.strip() + "\n" + right_text.strip()

    return page.extract_text() or ""


def extract_pdf_text(path):
    text = None
    try:
        import pdfplumber
        chunks = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                chunks.append(_extract_page_text(page))
        text = "\n".join(chunks).strip()
        if text:
            return text
    except Exception as e:
        logging.warning(f"pdfplumber failed on {path}: {e}")

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        chunks = [p.extract_text() or "" for p in reader.pages]
        text = "\n".join(chunks).strip()
    except Exception as e:
        logging.warning(f"PyPDF2 fallback failed on {path}: {e}")

    return text or None


def parse_product_page(url, extract_pdfs=True, category_membership=None, category_titles=None):
    resp = get(url)
    if resp is None:
        return None
    soup = BeautifulSoup(resp.text, "lxml")

    sku = url.rstrip("/").split("/")[-1].upper()

    # Fix: target the WooCommerce product title specifically, not the first
    # <h1> on the page (which is the "Catalogue" banner heading).
    product_h1 = soup.find("h1", class_="product_title") or soup.find("h1", class_=lambda c: c and "product_title" in c)
    name = product_h1.get_text(strip=True) if product_h1 else sku

    SECTION_HEADINGS = {"description", "downloads", "approvals", "related products", "notes"}
    subtitle_tag = product_h1.find_next(["h2", "h3"]) if product_h1 else None
    if subtitle_tag and subtitle_tag.get_text(strip=True).lower() in SECTION_HEADINGS:
        subtitle_tag = None
    subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else ""

    img_tag = soup.find("img", src=lambda s: s and ("uploads" in s))
    image = None
    if img_tag:
        image = img_tag.get("data-src") or img_tag.get("src")
        image = urljoin(BASE, image) if image else None
    # prefer the og:image meta if present, it's the full-res original
    og_img = soup.find("meta", attrs={"property": "og:image"})
    if og_img and og_img.get("content"):
        image = og_img["content"]

    # categories & tags: links to /product-category/ and /product-tag/
    categories = []
    tags = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/product-category/" in href:
            label = a.get_text(strip=True)
            if label and {"label": label, "url": urljoin(BASE, href)} not in categories:
                categories.append({"label": label, "url": urljoin(BASE, href)})
        elif "/product-tag/" in href:
            label = a.get_text(strip=True)
            if label and {"label": label, "url": urljoin(BASE, href)} not in tags:
                tags.append({"label": label, "url": urljoin(BASE, href)})

    specs, notes = parse_description_block(soup)
    downloads = parse_links_section(soup, "Downloads")
    approvals = parse_links_section(soup, "Approvals")
    related = parse_related_products(soup)

    if extract_pdfs:
        for section in (downloads, approvals):
            for item in section:
                if item["url"].lower().endswith(".pdf"):
                    result = download_and_extract_pdf(item["url"])
                    item["local_path"] = result["local_path"]
                    item["text"] = result["text"]

    # The category/sub-category URLs this product was actually found
    # listed under during the nav crawl (ground truth from the site's own
    # archive pages, not guessed from on-page text). Each becomes a
    # (top_category, sub_category, ...) slug path used to place this
    # product -- and therefore its PDFs -- in the right spot in the
    # output hierarchy.
    hierarchy_paths = []
    if category_membership:
        for cat_url in sorted(category_membership.get(url, [])):
            slug_path = category_slug_path(cat_url)
            if slug_path:
                hierarchy_paths.append({
                    "slug_path": list(slug_path),
                    "url": cat_url,
                    "title": (category_titles or {}).get(cat_url, slug_path[-1]),
                })

    # Deduplicate related products — remove "Read more" duplicates and keep
    # only entries whose label looks like a product SKU (e.g. HC-0200).
    seen_related = set()
    clean_related = []
    for r in related:
        if r["url"] not in seen_related and re.match(r"(?i)^[A-Z]{2,3}-\d{4}", r["label"]):
            seen_related.add(r["url"])
            clean_related.append({"sku": r["label"], "url": r["url"]})

    product = {
        "sku": sku,
        "name": name,
        "subtitle": subtitle,
        "url": url,
        "image": image,
        "categories": [c["label"] for c in categories],
        "tags": [t["label"] for t in tags],
        "specifications": specs,
        "notes": notes,
        "downloads": downloads,
        "approvals": approvals,
        "related_products": clean_related,
        "hierarchy_paths": hierarchy_paths,
    }
    return product


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def load_existing():
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def save_flat(products):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def build_hierarchy_tree(products, category_titles):
    """Nest products under Top Category -> Sub-category -> ... using each
    product's hierarchy_paths (derived from real nav membership, see
    discover_product_urls). A product with no detected category falls
    under '_uncategorized'. A product belonging to multiple sub-categories
    is placed under each one.

    Each leaf node embeds the full product record (not just the SKU) so
    the hierarchy JSON is self-contained and needs no second lookup.
    """
    # Build a SKU -> full product record index for embedding
    index = {p["sku"]: p for p in products}

    tree = {"name": "catalogue", "children": {}, "products": []}

    def get_node(path_parts):
        node = tree
        for i, part in enumerate(path_parts):
            node["children"].setdefault(part, {
                "name": part,
                "title": category_titles.get(
                    "/".join([BASE, "product-category"] + list(path_parts[: i + 1])) + "/",
                    part,
                ),
                "children": {},
                "products": [],
            })
            node = node["children"][part]
        return node

    for product in products:
        paths = product.get("hierarchy_paths") or []
        if not paths:
            get_node(("_uncategorized",))["products"].append(product["sku"])
            continue
        for hp in paths:
            get_node(tuple(hp["slug_path"]))["products"].append(product["sku"])

    def to_serializable(node):
        # Embed full product records; deduplicate by SKU preserving order
        seen = set()
        embedded = []
        for sku in node["products"]:
            if sku not in seen and sku in index:
                seen.add(sku)
                embedded.append(index[sku])
        return {
            "title": node.get("title", node["name"]),
            "products": embedded,
            "children": {k: to_serializable(v) for k, v in sorted(node["children"].items())},
        }

    return to_serializable(tree)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="only scrape first N products (testing)")
    parser.add_argument("--skip-pdf-text", action="store_true", help="don't download/parse PDFs")
    parser.add_argument("--resume", action="store_true", help="skip products already saved in products.json")
    args = parser.parse_args()

    setup_logging()

    urls, membership, category_titles = discover_product_urls()
    if args.limit:
        urls = urls[: args.limit]

    existing = load_existing() if args.resume else []
    done_urls = {p["url"] for p in existing}
    products = list(existing)

    for i, url in enumerate(urls, 1):
        if url in done_urls:
            logging.info(f"[{i}/{len(urls)}] skip (already done): {url}")
            continue
        logging.info(f"[{i}/{len(urls)}] scraping: {url}")
        try:
            product = parse_product_page(
                url,
                extract_pdfs=not args.skip_pdf_text,
                category_membership=membership,
                category_titles=category_titles,
            )
        except Exception as e:
            logging.exception(f"Failed to parse {url}: {e}")
            product = None
        if product:
            products.append(product)
            save_flat(products)  # save incrementally so progress isn't lost

    # flat index: sku -> product (fast lookup, no nesting/duplication)
    index = {p["sku"]: p for p in products}
    with open(os.path.join(OUT_DIR, "products_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    # nested tree mirroring the real category hierarchy (sku references only,
    # look the full record up in products_index.json / products.json)
    tree = build_hierarchy_tree(products, category_titles)
    with open(os.path.join(OUT_DIR, "hierarchy.json"), "w", encoding="utf-8") as f:
        json.dump(tree, f, ensure_ascii=False, indent=2)

    logging.info(
        f"Done. {len(products)} products saved to {JSON_PATH}, "
        f"plus products_index.json and hierarchy.json"
    )


if __name__ == "__main__":
    main()