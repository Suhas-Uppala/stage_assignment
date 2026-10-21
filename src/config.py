"""
Configuration settings for OTT Dialect Platform - One User, One Agent.
Loads configuration from environment variables and .env file.
"""
import os
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class AppConfig(BaseModel):
    # Base directories
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    CATALOGUE_DIR: str = os.getenv("CATALOGUE_DIR", "data/catalogue")
    FIXTURES_DIR: str = os.getenv("FIXTURES_DIR", "data/fixtures")
    SYNTHETIC_PACK_DIR: str = os.getenv("SYNTHETIC_PACK_DIR", "data/synthetic_pack")
    SAMPLE_RUN_DIR: str = os.getenv("SAMPLE_RUN_DIR", "sample_run")
    
    # Server & Dashboard
    DASHBOARD_HOST: str = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    DASHBOARD_PORT: int = int(os.getenv("DASHBOARD_PORT", "8050"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "sample_run/agent_state.db")
    
    # Operational limits & budgets
    MAX_EVENT_AGE_SECONDS: float = float(os.getenv("MAX_EVENT_AGE_SECONDS", "300.0"))  # 5 min stale threshold
    LATENCY_BUDGET_SECONDS: float = float(os.getenv("LATENCY_BUDGET_SECONDS", "60.0"))  # 60s target
    MAX_LATENCY_FAILURE_SECONDS: float = float(os.getenv("MAX_LATENCY_FAILURE_SECONDS", "300.0"))  # > 5 min failure
    MAX_MODEL_CALLS_PER_DECISION: int = int(os.getenv("MAX_MODEL_CALLS_PER_DECISION", "8"))
    MAX_TOOL_CALLS_PER_DECISION: int = int(os.getenv("MAX_TOOL_CALLS_PER_DECISION", "20"))
    
    # Messaging policy
    QUIET_HOURS_START: int = int(os.getenv("QUIET_HOURS_START", "22"))  # 22:00 local time
    QUIET_HOURS_END: int = int(os.getenv("QUIET_HOURS_END", "8"))     # 08:00 local time
    MAX_MESSAGES_PER_VIEWER_PER_DAY: int = int(os.getenv("MAX_MESSAGES_PER_VIEWER_PER_DAY", "1"))
    
    # Content constraints
    MIN_HOME_PAGE_TITLES: int = int(os.getenv("MIN_HOME_PAGE_TITLES", "3"))
    
    # LLM Settings & API Keys
    USE_MOCK_LLM: bool = os.getenv("USE_MOCK_LLM", "true").lower() in ("true", "1", "yes")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    LLM_TIMEOUT_SECONDS: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "5.0"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    
    # Commercial LLM Keys (Optional)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")


CONFIG = AppConfig()
