"""
PATCH FOR backend/main.py
Add these two lines alongside your existing router imports/includes.
Do NOT replace the whole file — just add these two lines.

--- IMPORT (alongside existing router imports) ---
from routers.invite_user import router as invite_router

--- INCLUDE (alongside existing app.include_router calls) ---
app.include_router(invite_router, prefix="/api")

--- CORS (confirm your existing CORS origins include your Vercel URL) ---
After deploy, add your Vercel prod URL to allow_origins.
Example:
    from fastapi.middleware.cors import CORSMiddleware

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",                 # local dev
            "https://your-app.vercel.app",           # Vercel prod — replace with your URL
            "https://your-custom-domain.com",        # if you add a custom domain later
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

--- HEALTH CHECK (confirm this exists, Railway uses it) ---
@app.get("/health")
def health():
    return {"status": "ok", "service": "ac-ebitda-backend"}
"""
