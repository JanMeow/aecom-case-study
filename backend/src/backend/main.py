from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.routers import advisories_router, assets_router, cv_router, llm_router, people_router, risk_router


#========================================
# App: one router per area (routers/); shared data and checks in routers/shared.py
#========================================
app = FastAPI(title="SGW Resilience Platform")

#========================================
# Middleware
#========================================
origins = [
    "http://localhost:5173"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(assets_router.router)       # /assets, /assets/{asset_id}
app.include_router(advisories_router.router)   # /advisories, /advisories/{advisory}/map
app.include_router(risk_router.router)         # /risks, /alerts
app.include_router(people_router.router)       # /people
app.include_router(llm_router.router)          # /llm/ask, /llm/report, /llm/playbook
app.include_router(cv_router.router)           # /cv/tree_canopy_pct


@app.get("/")
def health():
    return {"status": "ok"}
