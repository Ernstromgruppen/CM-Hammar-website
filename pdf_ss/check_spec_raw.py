import json, re

with open('output/hierarchy.json', encoding='utf-8') as f:
    h = json.load(f)

def all_products(node):
    prods = list(node.get('products') or [])
    for child in (node.get('children') or {}).values():
        prods.extend(all_products(child))
    return prods

products = all_products(h)
seen_sku = set(); unique = []
for p in products:
    if p['sku'] not in seen_sku:
        seen_sku.add(p['sku']); unique.append(p)

# Find raw text around SPECIFICATIONS heading in each data sheet
seen_text = set()
count = 0
for p in unique:
    for item in (p.get('downloads') or []):
        text = item.get('text', '')
        if not text:
            continue
        # Find SPECIFICATIONS section
        m = re.search(r'SPECIFICATIONS(.{0,600})', text, re.S)
        if not m:
            continue
        snippet = m.group(0)[:500]
        key = snippet[:80]
        if key in seen_text:
            continue
        seen_text.add(key)
        print(f"=== SKU: {p['sku']} ===")
        print(repr(snippet))
        print()
        count += 1
        if count >= 8:
            break
    if count >= 8:
        break
