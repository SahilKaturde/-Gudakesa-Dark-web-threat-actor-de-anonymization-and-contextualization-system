"""
extractor/patterns.py
Compiled regular expression patterns for darkweb text processing.
Covers multi-vendor marketplaces, single-vendor shops, forums, and listing archives.
"""
import re

# --- Prices (Fiat & Crypto) ---
PRICE_DOLLAR = re.compile(r"\$\s*([0-9,]+(?:\.[0-9]{2})?)")
PRICE_EURO = re.compile(r"[\u20ac\u00a3]\s*([0-9,]+(?:\.[0-9]{2})?)")
PRICE_BTC = re.compile(r"([0-9]+\.[0-9]{1,8})\s*(?:BTC|btc|Bitcoin)", re.I)
PRICE_XMR = re.compile(r"([0-9]+\.[0-9]{1,8})\s*(?:XMR|xmr|Monero)", re.I)
PRICE_CURRENT = re.compile(
    r"Current price is:\s*\$\s*([0-9,]+(?:\.[0-9]{2})?)", re.I
)
PRICE_ORIGINAL = re.compile(
    r"Original price was:\s*\$\s*([0-9,]+(?:\.[0-9]{2})?)", re.I
)
PRICE_STRIKETHROUGH = re.compile(r"~~\s*\$\s*([0-9,]+(?:\.[0-9]{2})?)\s*~~")
PRICE_RANGE = re.compile(
    r"\$\s*([0-9,]+(?:\.[0-9]{2})?)\s*[-\u2013\u2014]\s*\$\s*([0-9,]+(?:\.[0-9]{2})?)"
)

# --- Markdown Headings ---
H1_TITLE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
H2_SECTION = re.compile(r"^##\s+(.+)$", re.MULTILINE)
H3_SECTION = re.compile(r"^###\s+(.+)$", re.MULTILINE)
H4_SECTION = re.compile(r"^####\s+(.+)$", re.MULTILINE)

# --- Site Identity / Shop Name ---
SITE_TITLE_SUFFIX = re.compile(r"-\s*([A-Za-z0-9_\-\s]{3,40}?)(?:\s+Skip to|\s+Check link|\s*$)", re.I)
COPYRIGHT_VENDOR = re.compile(r"(?:Copyright|\u00a9)\s*\*\*([A-Za-z0-9_\-\s]{3,40})\*\*\s*\d{4}", re.I)
WELCOME_HEADER = re.compile(r"^#\s+Welcome\s+To\s+([A-Za-z0-9_\-\s]{3,40})$", re.MULTILINE | re.I)

# --- Ratings & Reviews ---
RATING_OVERALL = re.compile(
    r"[Rr]ated\s+\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+([0-9]+)"
)
RATING_BASED_ON = re.compile(
    r"[Rr]ated\s+\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+[0-9]+\s+"
    r"based on\s+(\d+)\s+customer\s+ratings?", re.I
)
REVIEW_COUNT = re.compile(r"\((\d+)\s+customer\s+reviews?\)", re.I)
REVIEW_SECTION_HEADER = re.compile(r"(\d+)\s+reviews?\s+for\s+(.+)", re.I)

# Primary darkweb review item regex:
REVIEW_ITEM_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:(\d+)\.\s*)?"
    r"[Rr]ated\s+\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+[0-9]+\s*\n+"
    r"(?:\*{1,2})?([^\n\-\u2013\u2014]+?)(?:\*{1,2})?\s*"
    r"[-\u2013\u2014]\s*"
    r"([A-Za-z]+\s+\d{1,2},?\s+\d{4})\s*\n+"
    r"([\s\S]*?)"
    r"(?=\n\s*\d+\.\s*[Rr]ated|\n\s*[Rr]ated\s+\*{0,2}[0-9]|\nAdd a review|\n##|\Z)",
    re.MULTILINE
)

# Secondary review pattern:
SIMPLE_REVIEW_PATTERN = re.compile(
    r"(?:Review by|User:?|Buyer:?)\s*\*\*?([A-Za-z0-9_\-\.\s]+?)\*\*?\s*"
    r"(?:[-\u2013\u2014]\s*([A-Za-z]+\s+\d{1,2},?\s+\d{4}))?\s*"
    r"(?:.*?([0-9](?:\.[0-9])?)\s*/\s*5)?\s*\n+"
    r"([\s\S]*?)"
    r"(?=\n(?:Review by|User:?|Buyer:?|##)|\Z)",
    re.MULTILINE | re.I
)

# --- Vendor / Seller Labels ---
VENDOR_INLINE = re.compile(r"(?:[Vv]endor|[Ss]eller|[Ss]old\s+by):\s{1,4}([A-Za-z0-9_\-\.\s&]+?)(?:\n|$)", re.I)

VENDOR_MULTILINE = re.compile(
    r"(?:^|\n)Vendor:?\s*\n+([A-Za-z0-9_\-\s&]{2,40}?)\s*\n+(?:\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+5)?",
    re.I
)

VENDOR_RATING = re.compile(r"\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+5")

# --- Breadcrumbs & Categories ---
BREADCRUMB = re.compile(r"Home\s*/\s*(.+?)(?:\n|$)", re.I)
CATEGORY_LABEL = re.compile(r"Categor(?:y|ies):?\s*([^\n]+)", re.I)
TAGS_LABEL = re.compile(r"Tags?:\s*([^\n]+)", re.I)
SKU_LABEL = re.compile(r"SKU:?\s*([^\n]+)", re.I)
AVAILABILITY = re.compile(r"(?:Availability|In stock|Stock):?\s*([^\n]+)", re.I)
ADD_TO_CART = re.compile(r"Add to cart", re.I)
SHOWING_RESULTS = re.compile(r"Showing\s+\d+[\u2013\-]\d+\s+of\s+\d+\s+results", re.I)

# --- Spec Tables ---
SPEC_TABLE_ROW = re.compile(
    r"^([A-Za-z][^\|]{1,40})\s*\|\s*(.+?)(?:\s*\|.*)?$", re.MULTILINE
)

# --- Sidebar / Navigation Sections ---
TOP_RATED_VENDORS_HEADER = re.compile(r"^##\s+Top Rated Vendors", re.MULTILINE | re.I)
PRODUCT_CATEGORIES_HEADER = re.compile(r"^##\s+Product categories", re.MULTILINE | re.I)
RECENT_COMMENTS_HEADER = re.compile(r"^##\s+Recent Comments", re.MULTILINE | re.I)
RECENT_COMMENT_ITEM = re.compile(r"\*\s+([^\n]+?)\s+on\s+([^\n]+)")
PRODUCT_TAGS_HEADER = re.compile(r"^##\s+Product tags", re.MULTILINE | re.I)
RELATED_PRODUCTS_HEADER = re.compile(r"^##\s+Related products", re.MULTILINE | re.I)
TOP_RATED_PRODUCTS_HEADER = re.compile(r"^##?\s+Top rated products", re.MULTILINE | re.I)

# --- Catalog / Archive Card Patterns ---
CATALOG_ITEM = re.compile(
    r"##\s+([^#\n]+?)\s*\n+"
    r"(?:[Rr]ated\s+\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+[0-9]+\s*\n+)?"
    r"(?:~~.*?~~.*\n+)?"
    r"(?:[^\n]*?(\$\s*[0-9,]+(?:\.[0-9]{2})?)[^\n]*?\n+)?"
    r"(?:Vendor:\s*([^\n\*]+?)\s*\n+(?:\*{0,2}([0-9.]+)\*{0,2}\s+out of\s+5)?)?",
    re.MULTILINE
)

ARCHIVE_ITEM = re.compile(
    r"^\s*\*\s+([A-Za-z0-9_\-\s&]+)\s*\n+"
    r"([^\n\$#\*][^\n]{2,100})\s*\n+"
    r"\$\s*([0-9,]+(?:\.[0-9]{2})?)\s*(?:Add to cart)?",
    re.MULTILINE
)

# --- Contact, Security & Financial Signals ---
ONION_DOMAIN = re.compile(r"([a-z2-7]{16,56}\.onion)", re.I)
EMAIL_ADDR = re.compile(r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)")
BTC_ADDRESS = re.compile(r"\b([13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b")
XMR_ADDRESS = re.compile(r"\b(4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}|8[0-9AB][1-9A-HJ-NP-Za-km-z]{93})\b")
TELEGRAM_HANDLE = re.compile(r"(?:t\.me/|@)([a-zA-Z0-9_]{5,32})")
JABBER_XMPP = re.compile(r"(?:xmpp|jabber):\s*([a-zA-Z0-9_.-]+@[a-zA-Z0-9_.-]+)", re.I)
