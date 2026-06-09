# CM Hammar — WordPress SEO & AI Optimisation Guide
### Step-by-step instructions for non-technical staff
**Prepared by:** Claude AI Assistant
**Date:** June 2026

---

## Before You Start

You will need:
- Access to **WordPress Admin** → `cmhammar.com/wp-admin`
- Access to **cPanel / File Manager** (ask your web host or IT person)
- Access to **Google Search Console** (free, takes 10 minutes to set up)

You do NOT need a developer for most of this. Everything below can be done by clicking — no coding required.

---

## PART 1 — Fix the SEO Plugin (1 hour)

The site currently uses **Yoast SEO** but it is not set up to generate product schema. This is the most important fix.

### Step 1 — Configure Yoast SEO for products

1. Log in to WordPress Admin → `cmhammar.com/wp-admin`
2. In the left menu click **SEO** → **Search Appearance**
3. Click the **Content Types** tab
4. Find **Products** in the list
5. Make sure **Show in search results** is set to **Yes**
6. Under **Schema**, set:
   - Page type → **Item Page**
   - Schema type → **Product**
7. Click **Save Changes**

### Step 2 — Add company information to Yoast

1. Left menu → **SEO** → **Search Appearance**
2. Click the **General** tab
3. Under **Knowledge Graph & Schema** fill in:
   - Organisation name: `CM Hammar AB`
   - Organisation logo: upload the CM Hammar logo
4. Click **Save Changes**

### Step 3 — Add social media profiles

1. Left menu → **SEO** → **Social**
2. Fill in each profile URL:
   - Facebook: `https://www.facebook.com/cmhammar/`
   - Instagram: `https://www.instagram.com/cm_hammar/`
   - LinkedIn: `https://www.linkedin.com/company/cm-hammar/`
   - YouTube: `https://www.youtube.com/channel/UCHEK0HWvACNGzfcbenKIHdg`
   - Twitter/X: `https://twitter.com/cm_hammar`
3. Click **Save Changes**

---

## PART 2 — Fix Product Pages (2–3 days, biggest job)

This is the most important part. Each product needs proper data filled in so Google and AI can read it correctly.

### Step 4 — Update each product one by one

For every product in the catalogue, do this:

1. Left menu → **Products** → **All Products**
2. Click on a product (e.g. HR-0100)
3. Fill in these fields:

**Basic fields (at the top of the page):**
- **Product name** — make it descriptive
  - Bad: `HC-0200`
  - Good: `HC-0200 H20 MRU Remote Dual Assembly Hydrostatic Release Unit`
- **Description (long)** — write 2–3 sentences about what the product does
  - Example: *"The HC-0200 is a dual assembly hydrostatic release unit for use with MRU liferafts and MES systems. It activates automatically at a depth of 1.5–4 metres. EC approved and SOLAS compliant."*
- **Short description** — one sentence summary

**Product data box (scroll down):**
- Click **General** tab → fill in **SKU** (e.g. `HC-0200`)
- Click **Attributes** tab → add these attributes one by one:
  - Attribute name: `Release Depth` → Value: `1.5 - 4 m`
  - Attribute name: `Weight` → Value: `0.31 kg`
  - Attribute name: `Breaking Strength` → Value: `Minimum 15 kN`
  - Attribute name: `Approvals` → Value: `EC Approved, MED, SOLAS`
  - Attribute name: `Certifications` → Value: `Bureau Veritas 07493/G0, MCA RedEnsign 73672/B0 UK`

**Yoast SEO box (scroll to bottom of page):**
- Click the **SEO** tab in the Yoast box
- Fill in **SEO title:**
  - Example: `HC-0200 H20 MRU Remote Dual Assembly | CM Hammar`
- Fill in **Meta description** (max 160 characters):
  - Example: `HC-0200 dual assembly HRU for MRU liferafts. Release depth 1.5–4m. EC approved, SOLAS compliant. Weight 0.31kg. CM Hammar AB.`

4. Click **Update** (blue button, top right)
5. Repeat for every product

> **Tip:** Do 5–10 products per day. It takes about 5 minutes per product once you get used to it.

---

## PART 3 — Upload the AI Files (30 minutes)

These two files tell AI systems (ChatGPT, Perplexity, Claude) about the site. They need to be placed on the web server.

### Step 5 — Upload llms.txt

`llms.txt` is a file we already created. It lists all products with full specifications in a format AI can read directly.

1. Log in to your web hosting control panel (cPanel, Plesk, or similar)
2. Open **File Manager**
3. Navigate to the **public_html** folder (this is the root of your website)
4. Click **Upload**
5. Upload the file `llms.txt` from this project
6. Done — it will be live at `https://www.cmhammar.com/llms.txt`

### Step 6 — Update robots.txt

`robots.txt` tells crawlers (Google, ChatGPT bots) that they are welcome.

**Option A — via Yoast (easiest):**
1. WordPress Admin → **SEO** → **Tools** → **File Editor**
2. Click **robots.txt**
3. Replace the contents with:

```
User-agent: *
Allow: /

User-agent: GPTBot
Allow: /

User-agent: Claude-Web
Allow: /

User-agent: PerplexityBot
Allow: /

User-agent: Googlebot
Allow: /

Sitemap: https://www.cmhammar.com/sitemap_index.xml
```

4. Click **Save changes to robots.txt**

**Option B — via File Manager (if Yoast option is greyed out):**
1. Go to File Manager → public_html
2. Find `robots.txt` — right click → Edit
3. Paste the content above
4. Save

---

## PART 4 — Submit to Google (15 minutes)

### Step 7 — Set up Google Search Console

Google Search Console is a free tool that lets you tell Google about your site directly.

1. Go to `https://search.google.com/search-console`
2. Sign in with a Google account
3. Click **Add Property**
4. Type `https://www.cmhammar.com` and click **Continue**
5. Follow the verification steps (Yoast makes this easy — it has a built-in verification option)

### Step 8 — Submit the sitemap

1. In Search Console, click **Sitemaps** in the left menu
2. In the box type: `sitemap_index.xml`
3. Click **Submit**

Google will now crawl all 178 pages within a few days instead of weeks.

### Step 9 — Request indexing for key pages

Do this for the most important pages to get them indexed fast:

1. In Search Console, click **URL Inspection** in the left menu
2. Paste this URL: `https://www.cmhammar.com/catalogue/hr-0100/`
3. Click **Request Indexing**
4. Repeat for 5–10 key products

---

## PART 5 — Add FAQ Sections to Key Pages (2 hours)

FAQ sections appear as expandable boxes directly in Google search results. They also help AI give structured answers.

### Step 10 — Add FAQ to a product page

1. WordPress Admin → **Products** → open any product
2. In the product description area, add a heading: `Frequently Asked Questions`
3. Below it, add questions and answers like this:

```
Q: Is the HR-0100 SOLAS approved?
A: Yes. The HR-0100 holds MED type approval (Marine Equipment Directive) 
and Bureau Veritas certification. It complies fully with SOLAS regulations 
for hydrostatic release units.

Q: How often must the HR-0100 be replaced?
A: Every 24 months (2 years) in accordance with SOLAS requirements. 
Annual inspection by an approved service station is also required.

Q: What depth does the HR-0100 activate at?
A: The HR-0100 activates automatically at a water depth of 1.5 to 4 metres.
```

4. If using the Gutenberg block editor — use the **FAQ block** (search for it in the block menu). Yoast automatically converts FAQ blocks into structured data.

---

## PART 6 — Validate Everything (30 minutes)

After making the changes, check they are working correctly.

### Step 11 — Test with Google Rich Results

1. Go to `https://search.google.com/test/rich-results`
2. Paste: `https://www.cmhammar.com/catalogue/hr-0100/`
3. Click **Test URL**
4. You should see: **Product**, **FAQ** detected ✅
5. If it shows errors — note what they say and contact your developer

### Step 12 — Test with Schema Validator

1. Go to `https://validator.schema.org`
2. Paste: `https://www.cmhammar.com`
3. Check that **Organization** schema appears with address and social links

### Step 13 — Test with AI

1. Go to `https://www.perplexity.ai`
2. Search: `CM Hammar HR-0100 specifications certifications`
3. The answer should now include release depth, weight, and certification numbers
4. If it does — the AI optimisation is working ✅

---

## Summary Checklist

Print this and tick off as you go:

- [ ] Yoast SEO configured for Products (Step 1)
- [ ] Company name and logo added to Yoast (Step 2)
- [ ] Social media profiles added to Yoast (Step 3)
- [ ] All product names, descriptions, attributes filled in (Step 4)
- [ ] `llms.txt` uploaded to server root (Step 5)
- [ ] `robots.txt` updated with AI crawler permissions (Step 6)
- [ ] Google Search Console set up (Step 7)
- [ ] Sitemap submitted to Google (Step 8)
- [ ] Key pages requested for indexing (Step 9)
- [ ] FAQ sections added to key product pages (Step 10)
- [ ] Validated with Rich Results Test (Step 11)
- [ ] Validated with Schema Validator (Step 12)
- [ ] Tested with Perplexity AI (Step 13)

---

## Who to Contact if Stuck

| Problem | Who to ask |
|---|---|
| Cannot log in to WordPress | IT / web developer |
| Cannot find File Manager | Web hosting company (e.g. WP Engine, Kinsta, SiteGround) |
| Yoast SEO options look different | Yoast documentation: yoast.com/help |
| Google Search Console verification fails | Web developer (takes 10 minutes) |
| Rich Results Test shows errors | Web developer |

---

## What This Achieves

Once all steps are complete, CM Hammar will have:

- Every product readable by ChatGPT, Perplexity, Google AI
- Rich product cards appearing directly in Google search results
- FAQ boxes appearing in Google search results for key products
- Full company identity (address, phone, social media) in AI search answers
- All 178 pages indexed by Google within days, not months
- No ongoing fees — everything runs automatically on the existing WordPress setup

**Total cost: EUR 0**
**Estimated time: 3–4 days for one person**
