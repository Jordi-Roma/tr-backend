import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:4200,http://127.0.0.1:4200,https://frontend-tr-production.up.railway.app",
    ).split(",")
    if origin.strip()
]
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
PASSWORD_RESET_EMAIL = os.getenv("PASSWORD_RESET_EMAIL", SMTP_USER)
PASSWORD_RESET_TOKEN_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "15"))

AI_REPORTS_PROVIDER = os.getenv("AI_REPORTS_PROVIDER", "RULES").upper()
AI_ASSISTANT_PROVIDER = os.getenv("AI_ASSISTANT_PROVIDER", "RULES").upper()
AI_RECOMMENDATIONS_PROVIDER = os.getenv("AI_RECOMMENDATIONS_PROVIDER", "RULES").upper()
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION") or os.getenv("GOOGLE_CLOUD_LOCATION", "global")
VERTEX_MODEL = os.getenv("VERTEX_MODEL", "gemini-2.5-flash")
VERTEX_EMBEDDING_MODEL = os.getenv("VERTEX_EMBEDDING_MODEL", "text-embedding-005")
