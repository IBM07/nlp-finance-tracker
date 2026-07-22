# ==========================================
# schemas.py — Pydantic Request/Response Schemas
# ==========================================
# Separate from SQLAlchemy models intentionally:
#   - SQLAlchemy models = database shape
#   - Pydantic schemas  = API contract (what goes in / comes out of the API)
#
# This separation lets us:
#   - Exclude sensitive fields (hashed_password) from API responses
#   - Add computed fields or rename columns without DB schema changes
#   - Version the API contract independently of the DB schema
# ==========================================

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Any, Literal
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


# ---------------------------------------------------------------------------
# Unified category taxonomy (Decision 5) — single source of truth shared by
# the LLM system prompts (llm.py, intent.py) and the frontend CATEGORIES array.
# ---------------------------------------------------------------------------

CATEGORIES = [
    "Food & Dining",
    "Transport",
    "Shopping",
    "Entertainment",
    "Healthcare",
    "Utilities",
    "Housing",
    "Business & Software",
    "Income",
    "Other",
]


# ---------------------------------------------------------------------------
# Finance / Query schemas
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Incoming natural-language query from the user."""
    question: str

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Question cannot be empty.")
        if len(v) > 500:
            raise ValueError("Question too long (max 500 characters).")
        return v


class QueryResponse(BaseModel):
    """Response from the /query endpoint."""
    sql: Optional[str] = None
    data: Optional[List[Any]] = None
    row_count: Optional[int] = None
    message: str


class FinanceEntryResponse(BaseModel):
    """Single finance entry returned from the database."""
    id: int
    user_id: int
    purchased: str
    categorization: str
    amount: Decimal
    date: str
    payment_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)   # allows ORM model → schema conversion


class AnalyticsItem(BaseModel):
    """One row of the analytics breakdown."""
    category: str
    total: Decimal


class RecentTransactionItem(BaseModel):
    """One row of the recent transactions list."""
    id: int
    item: str
    amount: Decimal
    category: str
    date: str


class FinanceEntryCreate(BaseModel):
    """Body for POST /finance/entries — manually add a transaction."""
    purchased: str
    categorization: str
    amount: Decimal
    date: str                        # YYYY-MM-DD
    payment_type: Optional[str] = None

    @field_validator("purchased")
    @classmethod
    def purchased_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Item name cannot be empty.")
        if len(v) > 255:
            raise ValueError("Item name too long (max 255 characters).")
        return v

    @field_validator("categorization")
    @classmethod
    def category_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Category cannot be empty.")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format.")
        return v


class FinanceEntryUpdate(BaseModel):
    """Body for PUT /finance/entries/{id} — manual edit by ID. All fields optional (partial patch)."""
    purchased: Optional[str] = None
    categorization: Optional[str] = None
    amount: Optional[Decimal] = None
    date: Optional[str] = None
    payment_type: Optional[str] = None

    @field_validator("purchased")
    @classmethod
    def purchased_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Item name cannot be empty.")
        if len(v) > 255:
            raise ValueError("Item name too long (max 255 characters).")
        return v

    @field_validator("categorization")
    @classmethod
    def category_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Category cannot be empty.")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        import re
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError("Date must be in YYYY-MM-DD format.")
        return v


# ---------------------------------------------------------------------------
# NLP intent schemas (LLM output shapes — Section 6.2)
# ---------------------------------------------------------------------------
# These model the four JSON structures the intent-extraction LLM may return.
# They are the boundary between untrusted LLM text and the application: the
# LLM's raw JSON is parsed into one of these before any service code touches it.
# ---------------------------------------------------------------------------

class IntentQuery(BaseModel):
    intent: Literal["QUERY"] = "QUERY"
    question: str


class IntentAdd(BaseModel):
    intent: Literal["ADD"] = "ADD"
    purchased: str
    categorization: str
    amount: Decimal
    type: Literal["expense", "income"]
    date: str = "today"                       # "YYYY-MM-DD" or the literal "today"
    payment_type: Optional[str] = None

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive.")
        return v


# Allowlist of fields an EDIT patch may touch — enforced again in service.py
# as the hard security boundary (Section 6.6: "LLM patches a disallowed field").
EDITABLE_FIELDS = {"purchased", "categorization", "amount", "date", "payment_type"}


class IntentEdit(BaseModel):
    intent: Literal["EDIT"] = "EDIT"
    target_description: Optional[str] = None
    target_id: Optional[int] = None
    patch: dict[str, Any] = {}

    @field_validator("patch")
    @classmethod
    def patch_keys_allowlisted(cls, v: dict[str, Any]) -> dict[str, Any]:
        disallowed = set(v.keys()) - EDITABLE_FIELDS
        if disallowed:
            raise ValueError(f"Patch contains disallowed fields: {sorted(disallowed)}")
        return v


class IntentDelete(BaseModel):
    intent: Literal["DELETE"] = "DELETE"
    target_description: Optional[str] = None
    target_id: Optional[int] = None


class ChatRequest(BaseModel):
    """Body for POST /finance/chat — the unified NLP endpoint (QUERY/ADD/EDIT/DELETE)."""
    message: str
    confirm_id: Optional[int] = None   # resolves an ambiguous EDIT/DELETE from a DisambiguationPanel choice

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty.")
        if len(v) > 500:
            raise ValueError("Message too long (max 500 characters).")
        return v


class ChatResponse(BaseModel):
    """Response from POST /finance/chat."""
    intent: str            # "QUERY" | "ADD" | "EDIT" | "DELETE" | "CONFIRM_NEEDED"
    message: str            # human-readable result
    data: Optional[Any] = None
    previous_state: Optional[Any] = None   # EDIT only — lets the frontend revert on Undo
    candidates: Optional[List[Any]] = None
    requires_confirmation: bool = False


class TranscribeResponse(BaseModel):
    """Response from POST /finance/transcribe — the voice-to-text transcript."""
    transcript: str


# ---------------------------------------------------------------------------
# Auth schemas (Phase 2 — fully implemented)
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    """Body for POST /auth/signup."""
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters.")
        return v


class LoginRequest(BaseModel):
    """Body for POST /auth/login."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Returned after a successful login or token refresh."""
    access_token: str
    refresh_token: str          # long-lived; use to obtain a new access token
    token_type: str = "bearer"
    expires_in: int             # seconds until access_token expires


class RefreshRequest(BaseModel):
    """Body for POST /auth/refresh and POST /auth/logout."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Body for POST /auth/change-password."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("New password must be at least 8 characters.")
        return v


class UserResponse(BaseModel):
    """Public-facing user info (never exposes hashed_password)."""
    id: int
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
