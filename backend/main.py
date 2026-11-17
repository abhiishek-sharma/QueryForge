import os

from dotenv import load_dotenv

load_dotenv()  # optional backend/.env; must run before app modules read env vars

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware

from app.api.sql_endpoints import router as sql_router

app = FastAPI(title="QueryForge API", version="0.2.0")

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["*"])
app.include_router(sql_router, prefix="/api/v1")


@app.get("/")
async def root():
    return {"message": "QueryForge API: natural-language questions to read-only SQL"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
