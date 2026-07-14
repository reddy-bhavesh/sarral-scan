import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "file:./dev.db"
    JWT_SECRET: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Kali Linux SSH Configuration (only used when EXECUTION_MODE=ssh)
    KALI_HOST: str = "10.77.145.71"
    KALI_PORT: int = 22
    KALI_USER: str = "kali"
    KALI_PASSWORD: Optional[str] = "kali"
    KALI_KEY_PATH: Optional[str] = None

    # Execution Mode: "local" (container) or "ssh" (remote Kali)
    EXECUTION_MODE: str = "local"

    # Google Gemini API (Primary)
    GEMINI_API_KEY: Optional[str] = "API_KEY"

    # Claude API (Anthropic) — fallback analyzer
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-opus-4-8"

    # Deep Agent mode (LangChain deepagents). DEEP_AGENT_MODEL falls back to
    # ANTHROPIC_MODEL when blank. Budget caps bound the orchestrator run.
    DEEP_AGENT_MODEL: str = ""
    DEEP_AGENT_MAX_STEPS: int = 24
    DEEP_AGENT_MAX_SECONDS: int = 3600

    # CTEM: CVE enrichment. NVD works without a key (5 req/30s); a key raises
    # the limit to 50 req/30s. EPSS and CISA KEV need no key.
    NVD_API_KEY: Optional[str] = None
    # Auto-match CVEs from detected software+version (Apache 2.4.52 → CVEs) via NVD.
    CVE_AUTO_MATCH: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore" # Allow extra fields in .env

settings = Settings()
