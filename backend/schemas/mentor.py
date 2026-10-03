"""schemas/mentor.py — AI Startup Mentor response schemas"""

from pydantic import BaseModel, Field
from typing import Optional, List


class MentorContact(BaseModel):
    """Contact information for a verified mentor."""
    email: Optional[str] = Field(None, description="Mentor email if available in verified record")
    phone: Optional[str] = Field(None, description="Mentor phone if available in verified record")
    linkedin: Optional[str] = Field(None, description="Mentor LinkedIn profile if available in verified record")


class VerifiedMentor(BaseModel):
    """A verified mentor from the mentor directory."""
    id: str = Field(..., description="Unique mentor ID from verified dataset")
    name: str = Field(..., description="Mentor full name")
    current_role: Optional[str] = Field(None, description="Current role or position")
    organization: Optional[str] = Field(None, description="Current organization or startup")
    expertise: List[str] = Field(default_factory=list, description="Areas of expertise")
    location: Optional[str] = Field(None, description="Geographic location")
    contact: Optional[MentorContact] = Field(None, description="Contact information if available")


class SectionItem(BaseModel):
    """An item within a response section."""
    title: str = Field(..., max_length=8, description="Item title (max 8 words)")
    description: str = Field(..., max_length=28, description="Item description (max 28 words)")


class Section(BaseModel):
    """A section of the mentor response."""
    heading: str = Field(..., max_length=8, description="Section heading (max 8 words)")
    items: List[SectionItem] = Field(default_factory=list, description="Items in this section")


class MentorResponse(BaseModel):
    """
    Stable mentor response contract.
    Used for both conversational answers and mentor recommendations.
    """
    type: str = Field(default="mentor_response", description="Response type identifier")
    title: Optional[str] = Field(None, description="Response title (short, direct)")
    summary: Optional[str] = Field(None, max_length=45, description="Summary text (max 45 words)")
    sections: List[Section] = Field(default_factory=list, description="Structured sections with items")
    mentors: List[VerifiedMentor] = Field(default_factory=list, description="Verified mentor recommendations")
    follow_up: Optional[str] = Field(None, max_length=20, description="Follow-up question (max 20 words)")
    fallback_text: Optional[str] = Field(None, description="Plain-text fallback if structured parsing fails")


class MentorChatRequest(BaseModel):
    """Request to the mentor chat endpoint."""
    message: str = Field(..., min_length=1, max_length=4000, description="User message")
    report_id: Optional[str] = Field(None, description="Optional report ID for context")
    structured: bool = Field(default=False, description="Request structured JSON response")


class MentorChatResponse(BaseModel):
    """Response from the mentor chat endpoint (SSE stream wrapper)."""
    message: str = Field(..., description="Response text or fallback")
    intent: str = Field(default="general_query", description="Detected intent")
    confidence: float = Field(default=0.0, description="Intent confidence score")
    structured_data: Optional[MentorResponse] = Field(None, description="Structured response if requested")
