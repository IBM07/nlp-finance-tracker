# ==========================================
# middleware/rate_limit.py — Shared Rate Limiter
# ==========================================
# Single Limiter instance imported by all routes.
# This avoids creating multiple limiter instances which would allow
# an attacker to bypass limits by hitting different endpoints.
# ==========================================

from slowapi import Limiter
from slowapi.util import get_remote_address

# Key function: rate-limit by IP.
# Phase 2: swap get_remote_address for a user-ID-based key function
# so that authenticated users get per-user limits (not per-IP).
limiter = Limiter(key_func=get_remote_address)
