from typing import List, Optional
from pydantic import BaseModel, Field


class ExtractFeatureRequest(BaseModel):
    domain_id: str
    page_id: str
    page_text: Optional[str] = None
    force_reextract: bool = False


class ExtractedEntityItem(BaseModel):
    feature_type: str = Field(
        description="Type of feature: username, email, ip, post, review, product, crypto_wallet, or other"
    )
    feature_value: str = Field(
        description="The exact extracted feature string value (e.g. 'dark_admin', 'admin@dread.onion', '192.168.1.1', '1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')"
    )
    context: str = Field(
        default="",
        description="A short context snippet (up to 150 chars) surrounding where this feature was found in the text"
    )
    description: str = Field(
        default="",
        description="Brief explanation of the threat relevance or context of this feature"
    )
    confidence_score: float = Field(
        default=0.8,
        description="Confidence score between 0.0 and 1.0 assessing accuracy of this extraction"
    )


class ExtractedFeatureBatch(BaseModel):
    features: List[ExtractedEntityItem] = Field(
        default_factory=list,
        description="List of extracted threat intelligence features found in the provided text"
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


class ExtractFeatureResponse(BaseModel):
    status: str
    message: str
    domain_id: str
    page_id: str
    extracted_count: int
    features: List[FeatureResponseItem]
