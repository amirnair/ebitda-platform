"""
backend/routers/invite_user.py

POST /api/invite-user
Admin/Owner only. Uses Supabase service_role key to send an invite email.
The invited user completes signup via the Supabase magic-link email.
handle_new_user() trigger auto-creates their profile from user_metadata.

Add to main.py:
    from routers.invite_user import router as invite_router
    app.include_router(invite_router, prefix="/api")
"""

import os
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, EmailStr
import httpx
from supabase import create_client, Client

router = APIRouter()

SUPABASE_URL         = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

# Service-role client — never expose this key to the frontend
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str          # owner | admin | finance | production | sales | viewer
    company_id: str    # UUID of the company the invited user will belong to


VALID_ROLES = {"owner", "admin", "finance", "production", "sales", "viewer"}


async def _get_calling_user_role(authorization: str) -> dict:
    """
    Validate the Bearer token and return the caller's profile row.
    Raises 401/403 on failure.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]

    # Verify token with Supabase
    try:
        user_resp = supabase_admin.auth.get_user(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

    user = user_resp.user
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Fetch calling user's profile
    profile_resp = (
        supabase_admin
        .from_("profiles")
        .select("role, company_id, is_active")
        .eq("id", user.id)
        .single()
        .execute()
    )
    if not profile_resp.data:
        raise HTTPException(status_code=403, detail="Caller profile not found")

    profile = profile_resp.data
    if not profile.get("is_active"):
        raise HTTPException(status_code=403, detail="Caller account is inactive")

    return profile


@router.post("/invite-user")
async def invite_user(
    body: InviteUserRequest,
    authorization: str = Header(None),
):
    """
    Send a Supabase invite email to a new user.
    - Caller must be owner or admin of the same company.
    - Invited user's profile is auto-created by the handle_new_user() trigger
      using the user_metadata we pass here.
    """

    # 1. Authenticate caller
    caller = await _get_calling_user_role(authorization)

    # 2. Authorise: caller must be owner/admin AND in the same company
    if caller["role"] not in ("owner", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Only owners and admins can invite users"
        )
    if caller["company_id"] != body.company_id:
        raise HTTPException(
            status_code=403,
            detail="Cannot invite users to a different company"
        )

    # 3. Validate role value
    if body.role not in VALID_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid role '{body.role}'. Must be one of: {', '.join(VALID_ROLES)}"
        )

    # 4. Prevent inviting another owner (only one owner per company)
    if body.role == "owner":
        existing_owner = (
            supabase_admin
            .from_("profiles")
            .select("id")
            .eq("company_id", body.company_id)
            .eq("role", "owner")
            .execute()
        )
        if existing_owner.data:
            raise HTTPException(
                status_code=409,
                detail="Company already has an owner. Change the existing owner's role first."
            )

    # 5. Send Supabase invite — user_metadata is picked up by handle_new_user() trigger
    try:
        # Supabase Python SDK v2: auth.admin.invite_user_by_email
        response = supabase_admin.auth.admin.invite_user_by_email(
            body.email,
            options={
                "data": {
                    "company_id": body.company_id,
                    "full_name":  body.full_name,
                    "role":       body.role,
                }
            }
        )
    except Exception as e:
        error_msg = str(e)
        # Surface common errors clearly
        if "already registered" in error_msg.lower() or "email address already" in error_msg.lower():
            raise HTTPException(
                status_code=409,
                detail="A user with this email address already exists."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Supabase invite failed: {error_msg}"
        )

    return {
        "success": True,
        "message": f"Invite sent to {body.email}",
        "invited_user_id": str(response.user.id) if response.user else None,
    }
