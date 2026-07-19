# ==========================================
# finance/routes.py — Finance API Endpoints
# ==========================================
# All routes are user-scoped via get_current_user() JWT dependency.
# Phase 2: Replaced hardcoded user_id=1 stub with real authentication.
# ==========================================

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import (
    QueryRequest,
    QueryResponse,
    FinanceEntryCreate,
    FinanceEntryUpdate,
    ChatRequest,
    ChatResponse,
    IntentAdd,
    IntentDelete,
    IntentEdit,
    IntentQuery,
)
from app.finance import service
from app.finance.intent import classify_and_extract, IntentExtractionError
from app.finance.sql_guard import SQLGuardError
from app.middleware.rate_limit import limiter
from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/finance", tags=["finance"])


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
def process_query(
    request: Request,
    req: QueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Natural-language → SQL → results pipeline.
    The query is always scoped to the authenticated user via JWT.
    """
    user_id = current_user.id
    logger.info("Query request from user_id=%s: %r", user_id, req.question)
    try:
        result = service.run_nl_query(
            question=req.question,
            user_id=user_id,
            db=db,
        )
        return QueryResponse(**result)
    except SQLGuardError as e:
        logger.warning("SQL guard rejected query for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=400, detail=f"Query blocked by security validator: {e}")
    except RuntimeError as e:
        logger.error("LLM unavailable for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")
    except Exception as e:
        logger.exception("Unexpected error processing query for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error.")


@router.get("/analytics")
@limiter.limit("60/minute")
def get_analytics(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns spending breakdown by category for the current authenticated user."""
    user_id = current_user.id
    logger.info("Analytics requested for user_id=%s", user_id)
    try:
        data = service.get_analytics(user_id=user_id, db=db)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.exception("Analytics error for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to fetch analytics.")


@router.get("/summary")
@limiter.limit("60/minute")
def get_summary(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns KPI figures (current vs. previous month) for the dashboard metric cards."""
    user_id = current_user.id
    logger.info("Summary requested for user_id=%s", user_id)
    try:
        data = service.get_summary(user_id=user_id, db=db)
        return {"status": "success", "data": data}
    except Exception:
        logger.exception("Summary error for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to fetch summary.")


@router.get("/recent")
@limiter.limit("60/minute")
def get_recent_transactions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the 5 most recent transactions for the current authenticated user."""
    user_id = current_user.id
    logger.info("Recent transactions requested for user_id=%s", user_id)
    try:
        data = service.get_recent(user_id=user_id, db=db)
        return {"status": "success", "data": data}
    except Exception as e:
        logger.exception("Recent data error for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to fetch recent transactions.")


@router.post("/entries", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
def create_entry(
    request: Request,
    req: FinanceEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually add a finance entry for the authenticated user.
    This is the write counterpart to /query (which is read-only SELECT).
    """
    user_id = current_user.id
    logger.info(
        "Create entry request from user_id=%s: %s %.2f",
        user_id, req.purchased, req.amount,
    )
    try:
        entry = service.create_entry(
            user_id=user_id,
            data=req.model_dump(),
            db=db,
        )
        return {"status": "success", "data": entry}
    except Exception:
        logger.exception("Failed to create entry for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Failed to create transaction.")


@router.put("/entries/{entry_id}")
@limiter.limit("60/minute")
def update_entry_route(
    entry_id: int,
    request: Request,
    req: FinanceEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually update a finance entry by ID. Used by inline table edits, the
    edit-mode AddTransactionModal, and the frontend's Undo-restore call.
    """
    user_id = current_user.id
    logger.info("Update entry request from user_id=%s for entry_id=%s", user_id, entry_id)
    try:
        entry = service.update_entry(
            user_id=user_id,
            entry_id=entry_id,
            data=req.model_dump(exclude_unset=True),
            db=db,
        )
        return {"status": "success", "data": entry}
    except service.EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to update entry_id=%s for user_id=%s", entry_id, user_id)
        raise HTTPException(status_code=500, detail="Failed to update transaction.")


@router.delete("/entries/{entry_id}")
@limiter.limit("60/minute")
def delete_entry_route(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Manually delete a finance entry by ID. Used by inline table deletes and by
    the delayed-API-execution Undo pattern (both manual and NLP deletes).
    """
    user_id = current_user.id
    logger.info("Delete entry request from user_id=%s for entry_id=%s", user_id, entry_id)
    try:
        entry = service.delete_entry(user_id=user_id, entry_id=entry_id, db=db)
        return {"status": "success", "data": entry}
    except service.EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("Failed to delete entry_id=%s for user_id=%s", entry_id, user_id)
        raise HTTPException(status_code=500, detail="Failed to delete transaction.")


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("10/minute")
def chat(
    request: Request,
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified conversational endpoint (Section 4 of the feature plan).

    Classifies the raw prompt into QUERY / ADD / EDIT / DELETE via
    classify_and_extract(), then executes the corresponding safe operation.
    The LLM only ever produces typed JSON that is Pydantic-validated — it
    NEVER generates SQL for mutations, and user_id always comes from the JWT,
    never from LLM output (Section 3 — non-negotiable).
    """
    user_id = current_user.id
    logger.info("Chat request from user_id=%s: %r", user_id, req.message)

    try:
        intent_data = classify_and_extract(req.message, user_id)
    except IntentExtractionError as e:
        logger.warning("Intent extraction failed for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=422, detail=str(e))

    try:
        if isinstance(intent_data, IntentQuery):
            result = service.run_nl_query(question=intent_data.question, user_id=user_id, db=db)
            return ChatResponse(intent="QUERY", message=result["message"], data=result["data"])

        if isinstance(intent_data, IntentAdd):
            entry = service.create_entry_from_nlp(
                user_id=user_id, intent_data=intent_data, prompt=req.message, db=db,
            )
            return ChatResponse(
                intent="ADD",
                message=f"Added \"{entry['item']}\" · {entry['amount']} · {entry['category']}",
                data=entry,
            )

        if isinstance(intent_data, IntentEdit):
            if req.confirm_id is not None:
                intent_data.target_id = req.confirm_id
            result = service.update_entry_from_nlp(
                user_id=user_id, intent_data=intent_data, prompt=req.message, db=db,
            )
            if result["requires_confirmation"]:
                return ChatResponse(
                    intent="CONFIRM_NEEDED",
                    message="I found multiple matches. Which one did you mean?",
                    candidates=result["candidates"],
                    requires_confirmation=True,
                )
            return ChatResponse(
                intent="EDIT",
                message="Transaction updated.",
                data=result["data"],
                previous_state=result["previous_state"],
            )

        if isinstance(intent_data, IntentDelete):
            if req.confirm_id is not None:
                intent_data.target_id = req.confirm_id
            result = service.delete_entry_from_nlp(
                user_id=user_id, intent_data=intent_data, prompt=req.message, db=db,
            )
            if result["requires_confirmation"]:
                return ChatResponse(
                    intent="CONFIRM_NEEDED",
                    message="I found multiple matches. Which one did you mean?",
                    candidates=result["candidates"],
                    requires_confirmation=True,
                )
            return ChatResponse(intent="DELETE", message="Transaction deleted.", data=result["data"])

        logger.error("Unhandled intent type for user_id=%s: %r", user_id, intent_data)
        raise HTTPException(status_code=500, detail="Internal server error.")

    except service.EntryNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SQLGuardError as e:
        logger.warning("SQL guard rejected chat query for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=400, detail=f"Query blocked by security validator: {e}")
    except RuntimeError as e:
        logger.error("LLM unavailable for user_id=%s: %s", user_id, e)
        raise HTTPException(status_code=503, detail="AI service temporarily unavailable.")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception:
        logger.exception("Unexpected error processing chat for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Internal server error.")

