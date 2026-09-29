from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractFeatureRequest(BaseModel):
    domain_id: str
    page_id: str
    page_text: Optional[str] = None
    force_reextract: bool = False


class ExtractedEntityItem(BaseModel):
    feature_type: str = Field(
        description="Type of feature: username, email, ip, phone, financial_account, "
                    "post, review, product, crypto_wallet, pgp_key, onion_url, xmpp, or other"
    )
    feature_value: str = Field(
        description="The exact extracted feature string value"
    )
    context: str = Field(
        default="",
        description="A short verbatim context snippet (up to ~250 chars) surrounding where this feature was found."
    )
    description: str = Field(
        default="",
        description=(
            "Analytical write-up of this feature's threat relevance: "
            "what it is, why it matters, confidence rationale, and recommended next step."
        )
    )
    confidence_score: float = Field(
        default=0.8,
        description="Confidence score between 0.0 and 1.0"
    )

    # --- Investigative metadata -----------------------------------------------
    short_label: Optional[str] = Field(
        default=None,
        description="Compact 3-6 word tag for UI badges/lists."
    )
    category: Optional[str] = Field(
        default=None,
        description="High-level bucket: identity, communication, financial, infrastructure, activity, or other."
    )
    risk_level: Optional[str] = Field(
        default=None,
        description="Investigative risk: low, medium, high, or critical."
    )
    actor_role: Optional[str] = Field(
        default=None,
        description="Role: vendor, buyer, admin, moderator, or unknown."
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Freeform investigative keywords."
    )
    related_indicators: List[str] = Field(
        default_factory=list,
        description="Other feature_values found nearby that appear connected."
    )

    # --- Source provenance (NEW) — powers the frontend line-highlight feature --
    source_line_start: Optional[int] = Field(
        default=None,
        description="1-based line number in the source document where this feature was found (start)."
    )
    source_line_end: Optional[int] = Field(
        default=None,
        description="1-based line number in the source document where this feature ends."
    )
    source_method: Optional[str] = Field(
        default=None,
        description="Extraction method: regex, regex_review, regex_vendor, regex_archive, regex_card, llm."
    )
    page_type: Optional[str] = Field(
        default=None,
        description="Classified page type: PRODUCT_DETAIL, CATALOG_LISTING, or GENERAL."
    )


class ExtractedFeatureBatch(BaseModel):
    features: List[ExtractedEntityItem] = Field(
        default_factory=list,
        description="List of extracted threat intelligence features"
    )


class FeatureResponseItem(BaseModel):
    feature_id: str
    domain_id: str
    page_id: str
    feature_type: str
    feature_value: str
    context: str
    description: str
    confidence_score: Optional[float]
    extracted_timestamp: Optional[str] = None

    # Investigative metadata
    short_label: Optional[str] = None
    category: Optional[str] = None
    risk_level: Optional[str] = None
    actor_role: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    related_indicators: List[str] = Field(default_factory=list)

    # Source provenance — for frontend line-highlight hyperlinks
    source_line_start: Optional[int] = None
    source_line_end: Optional[int] = None
    source_method: Optional[str] = None
    page_type: Optional[str] = None


class ExtractFeatureResponse(BaseModel):
    status: str
    message: str
    domain_id: str
    page_id: str
    extracted_count: int
    features: List[FeatureResponseItem]