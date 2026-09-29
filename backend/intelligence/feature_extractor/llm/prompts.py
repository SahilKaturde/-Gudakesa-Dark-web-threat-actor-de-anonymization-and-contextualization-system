"""
extractor/llm/prompts.py
Focused micro-prompts tailored for qwen3:1.7b (single-task prompts for clean extraction).
"""

PRODUCT_EXTRACTION = """/no_think
Extract product information from this darkweb text.
Return ONLY valid JSON (no extra text):
{{"product_name": "", "price": "", "category": "", "vendor": "", "in_stock": ""}}

Text:
---
{chunk}
---
JSON:"""

REVIEW_EXTRACTION = """/no_think
Extract customer reviews and user feedback from this darkweb text.
Return ONLY a JSON array. Each object: {{"username": "", "rating": null, "date": "", "comment": ""}}
If no reviews found, return []

Text:
---
{chunk}
---
JSON:"""

VENDOR_EXTRACTION = """/no_think
Extract vendor/seller or shop profile from this darkweb text.
Return ONLY valid JSON: {{"vendor_name": "", "vendor_rating": null, "contact_info": ""}}
If no vendor info found, return {{"vendor_name": null}}

Text:
---
{chunk}
---
JSON:"""

PAGE_SUMMARY = """/no_think
You are a darkweb intelligence analyst. Write a concise 2-sentence investigative summary of this page (what is offered/discussed, prices, vendors, operational notes):

Text:
---
{chunk}
---
Investigative Summary:"""

CHUNK_MERGE_SUMMARY = """/no_think
Combine these partial notes into one crisp 2-3 sentence executive intelligence summary:

{summaries}

Final Intelligence Summary:"""
