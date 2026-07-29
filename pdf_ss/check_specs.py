import json
with open('output/hierarchy.json', encoding='utf-8') as f:
    h = json.load(f)

def all_products(node):
    prods = list(node.get('products') or [])
    for child in (node.get('children') or {}).values():
        prods.extend(all_products(child))
    return prods

products = all_products(h)
seen = set(); unique = []
for p in products:
    if p['sku'] not in seen:
        seen.add(p['sku']); unique.append(p)

def get_ds(p):
    for item in (p.get('downloads') or []):
        s = item.get('structured') or {}
        if isinstance(s, dict) and s.get('document_type') == 'data_sheet':
            return s
    return None

count = 0
for p in unique:
    ds = get_ds(p)
    if ds:
        spec = ds.get('sections', {}).get('SPECIFICATIONS')
        if spec:
            print(f"SKU: {p['sku']}")
            print(f"  type: {type(spec).__name__}")
            print(f"  value: {json.dumps(spec, ensure_ascii=False)[:400]}")
            print()
            count += 1
    if count >= 5:
        break
