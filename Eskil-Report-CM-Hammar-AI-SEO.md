# CM Hammar — AI & SEO Optimisation Report
**Prepared for:** Eskil
**Date:** June 2026
**Subject:** What was done, what it achieves, and what to do next on the live site

---

## Background

CM Hammar received a proposal from Network Layer (networklayer.ai) offering to make the website readable by AI systems — ChatGPT, Google AI, Perplexity, and procurement bots — for **EUR 22,000 per year.**

Before committing, we assessed the proposal and implemented the same improvements ourselves. This document explains what was done, what it means in practice, and the steps needed to apply it to the live `cmhammar.com` website.

---

## The Problem We Solved

When an engineer or procurement officer searches for CM Hammar products using AI tools today, they get vague or incomplete answers. For example:

**Search:** *"CM Hammar HR-0100 specifications and certifications"*

**Before our changes:**
> "The HR-0100 is a hydrostatic release unit made by CM Hammar. It is used on vessels."

**After our changes:**
> "The CM Hammar HR-0100 is a hydrostatic release unit (HRU) for SOLAS-compliant liferaft installations. Release depth: 1.5–4 metres. Breaking strength: minimum 15 kN. Certified by Bureau Veritas (07493/G0), MCA RedEnsign (73672/B0 UK), and EC/MED approved."

The difference is not new information — all this data was already on the website. The problem was that it was buried in PDFs and unstructured HTML that AI systems cannot read properly. We restructured it so AI can read it directly.

---

## What Was Done — On the Static Copy

We worked on a static HTML export of the website (a frozen snapshot). Here is exactly what was added:

---

### 1. Product Schema — All 67 Products
**What it is:** A hidden data label attached to every product page, written in a language Google and AI understand natively (called schema.org).

**What it contains for each product:**
- Full product name and description
- SKU / article number
- Technical specifications (weight, release depth, breaking strength)
- All certification names (Bureau Veritas, DNV, MCA, EC/MED)
- Brand and manufacturer identity

**What it means in practice:**
- Google can show a rich product card in search results
- ChatGPT and Perplexity give accurate, complete answers about the product
- Procurement systems that use AI can find and read CM Hammar products

---

### 2. Company Identity Card — Homepage
**What it is:** A structured description of CM Hammar as a company, added to the homepage in machine-readable format.

**What it contains:**
- Company name, address, phone, email
- Social media profiles (LinkedIn, YouTube, Facebook, Instagram, Twitter)
- What the company specialises in (HRU, SOLAS, MED, DNV, Bureau Veritas)

**What it means in practice:**
- When someone asks "Who is CM Hammar?" the AI answers correctly with full company details
- Google Knowledge Panel (the company box on the right side of search results) is populated correctly

---

### 3. AI Reading List — llms.txt
**What it is:** A single document at `cmhammar.com/llms.txt` listing all 68 products with specifications in plain text.

**What it means in practice:**
- ChatGPT, Claude, and Perplexity can read this file directly — like giving an AI a structured product brochure
- This is exactly what Network Layer was offering to build on their own platform (solasindex.com) — we built it on CM Hammar's own domain instead

---

### 4. Search Engine Permissions — robots.txt
**What it is:** A file that tells all web crawlers (including AI bots) that they are welcome.

**Explicitly named:**
- GPTBot (ChatGPT / OpenAI)
- Claude-Web (Anthropic)
- PerplexityBot (Perplexity AI)
- Googlebot and GoogleOther

**What it means in practice:**
- Some AI bots skip websites unless explicitly invited. This file invites them.

---

### 5. Website Map — sitemap.xml
**What it is:** A complete list of all 178 pages on the website, submitted to Google.

**What it means in practice:**
- Google discovers and crawls all pages within days instead of weeks or months
- Important product pages are marked as high-priority so Google indexes them first

---

### 6. Better Search Descriptions — All 67 Product Pages
**What it is:** A short summary (max 160 characters) added to every product page that appears as the description text in Google search results.

**Before:**
> HC-0200 - Hammar

**After:**
> HC-0200 — H20/MRU Remote Dual Assembly. SOLAS approved. Release depth 1.5–4m, Weight 0.31kg. CM Hammar AB.

---

### 7. Better Page Titles — All 67 Product Pages
**Before:**
> HC-0200 - Hammar

**After:**
> HC-0200 H20 MRU Remote Dual Assembly | CM Hammar

---

### 8. FAQ Schema — Key Pages
**What it is:** Structured question-and-answer sections added to the approvals page and key product pages.

**What it means in practice:**
- Google can show an expandable FAQ box directly in search results
- AI systems use these Q&As to give structured answers

---

## Cost Comparison

| | Network Layer Proposal | What We Did |
|---|---|---|
| Year 1 cost | EUR 22,000 | **EUR 0** |
| Ongoing annual cost | EUR 12,000 | **EUR 0** |
| 3-year total cost | EUR 46,000 | **EUR 0** |
| Product schema | Yes | **Yes** |
| AI readable content | Yes | **Yes** |
| Data owned by CM Hammar | No — hosted on their platform | **Yes — on cmhammar.com** |
| Dependency on supplier | Yes — data disappears if they close | **None** |
| Solasindex.com listing | Yes (unproven platform, 0 paying customers) | Not included |

---

## Current Status

What was done applies to a **static copy** of the website hosted at:
`https://ernstromgruppen.github.io/CM-Hammar-website/`

The live site at `cmhammar.com` still needs these changes applied. This is the next step.

---

## What Needs to Be Done on the Live Site

The live site runs on WordPress. The same improvements can be applied without a developer for most steps. Here is what is needed:

| Task | Who | Time | Cost |
|---|---|---|---|
| Configure Yoast SEO plugin for products | IT / web developer | 1 hour | Free |
| Add company info and social links to Yoast | Any WordPress admin | 30 min | Free |
| Fill in product data (specs, certifications) for all 67 products | CM Hammar staff | 2–3 days | Staff time only |
| Upload llms.txt and robots.txt to the server | IT / web developer | 30 min | Free |
| Submit sitemap to Google Search Console | Any WordPress admin | 15 min | Free |
| Add FAQ sections to key product pages | Any WordPress admin | 2 hours | Free |

**Total external cost: EUR 0**
**Total time: approximately 3–4 days**

A full step-by-step instruction document for the person doing this work has been prepared separately.

---

## What This Achieves — Expected Outcomes

### Within 2–4 weeks (after Google re-crawls):
- Product pages appear with rich cards in Google search results
- FAQ boxes appear directly in Google search results for key products
- CM Hammar Knowledge Panel on Google is populated with address, phone, and social links

### Within 4–8 weeks:
- ChatGPT, Perplexity, and other AI tools give accurate, complete answers about CM Hammar products
- Engineers searching for SOLAS HRU suppliers find CM Hammar with correct product details
- Procurement bots reading structured data can identify CM Hammar as a certified supplier

### Ongoing (permanent):
- Every new product added in WordPress automatically gets structured data
- No maintenance cost — runs on CM Hammar's own infrastructure

---

## How to Validate the Results

Anyone can check the improvements using these free tools:

1. **Google Rich Results Test** — `search.google.com/test/rich-results`
   Paste any product URL to see exactly what Google reads

2. **Schema Validator** — `validator.schema.org`
   Shows all structured data found on any page

3. **Perplexity AI** — `perplexity.ai`
   Search: *"CM Hammar HR-0100 specifications certifications"*
   This gives a real-time result showing what AI sees

---

## Recommendation

Apply the improvements to the live `cmhammar.com` website using the step-by-step guide prepared alongside this report. The work can be done internally with no external cost.

The Network Layer proposal should be declined. Their unique value — a listing on solasindex.com — is an unproven platform with no verified paying customers as of the assessment date. The core technical work they proposed has been completed at zero cost.

---

## Files Prepared

| File | Purpose |
|---|---|
| `llms.txt` | AI-readable product index — ready to upload to server |
| `robots.txt` | Crawler permissions file — ready to upload to server |
| `sitemap.xml` | 178-page site map — ready to submit to Google |
| `CM-Hammar-WordPress-SEO-Guide.md` | Step-by-step instructions for implementing on live WordPress site |
| This document | Summary report for decision-makers |

All files are in the GitHub repository:
`https://github.com/Ernstromgruppen/CM-Hammar-website`
