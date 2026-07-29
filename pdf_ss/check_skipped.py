import json, os

with open('output/products.json', encoding='utf-8') as f:
    products = json.load(f)

by_sku = {p['sku'].upper(): p for p in products}

skipped = [
    'HC-0215','HC-0325','HC-0340',
    'HE-0021','HE-0022','HE-0023','HE-0024','HE-0028',
    'HE-0030','HE-0031','HE-0041','HE-0045',
    'HM-0461','HM-0710','HM-0725','HM-0807',
    'HR-0200','HR-0500','HR-0501','TR-0001'
]

for sku in skipped:
    p = by_sku.get(sku)
    if not p:
        print(f"{sku}: NOT IN products.json at all")
        continue
    downloads = p.get('downloads') or []
    print(f"\n{sku} — {p.get('subtitle','')}")
    print(f"  Downloads: {len(downloads)}")
    for d in downloads:
        s = d.get('structured') or {}
        doc_type = s.get('document_type', 'NOT STRUCTURED') if isinstance(s, dict) else 'NULL'
        local = d.get('local_path', 'no local path')
        pdf_exists = os.path.exists(os.path.join('output', local.replace('\\', os.sep))) if local else False
        print(f"  - [{doc_type}] {d.get('name','')[:60]} | pdf_exists={pdf_exists}")
