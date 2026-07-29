import json, os

with open('output/products.json', encoding='utf-8') as f:
    products = json.load(f)

by_sku = {p['sku'].upper(): p for p in products}

skipped = [
    'HC-0215','HC-0325','HC-0340',
    'HE-0021','HE-0022','HE-0023','HE-0024','HE-0028',
    'HE-0030','HE-0031','HE-0041','HE-0045',
    'HM-0461','HM-0710','HM-0725',
    'HR-0200','HR-0500','HR-0501','TR-0001'
]

for sku in skipped:
    p = by_sku.get(sku)
    if not p:
        print(f"\n{'='*60}\n{sku}: NOT IN products.json")
        continue

    print(f"\n{'='*60}")
    print(f"{sku} — {p.get('subtitle','')}")
    print(f"  specifications: {json.dumps(p.get('specifications'), ensure_ascii=False)}")
    print(f"  notes: {p.get('notes','')[:100]}")
    print(f"  tags: {p.get('tags')}")
    print(f"  categories: {p.get('categories')}")

    for section in ('downloads', 'approvals'):
        for item in (p.get(section) or []):
            s = item.get('structured')
            print(f"\n  [{section}] {item.get('name','')[:70]}")
            if s is None:
                print(f"    structured: NULL")
            elif isinstance(s, dict):
                print(f"    document_type: {s.get('document_type')}")
                # Print all keys and their values
                for k, v in s.items():
                    if k == 'document_type':
                        continue
                    val_str = json.dumps(v, ensure_ascii=False)
                    if len(val_str) > 200:
                        val_str = val_str[:200] + '...'
                    print(f"    {k}: {val_str}")
            else:
                print(f"    structured: {str(s)[:200]}")
