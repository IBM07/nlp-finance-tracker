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
from app.schemas import QueryRequest, QueryResponse, FinanceEntryCreate
from app.finance import service
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

