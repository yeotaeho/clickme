from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# 프로젝트 루트의 .env 파일을 찾음 (backend/ 위 상위 디렉토리)
_ENV_FILE = Path(__file__).parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    # DB & 캐시
    DATABASE_URL: str
    REDIS_URL: str

    # LLM API 키
    OPENAI_API_KEY: str
    ANTHROPIC_API_KEY: str = ""

    # OAuth (소셜 로그인)
    KAKAO_CLIENT_ID: str = ""
    NAVER_CLIENT_ID: str = ""
    GOOGLE_CLIENT_ID: str = ""

    # 런타임 설정
    DEFAULT_PERSONA_COUNT: int = 20
    MAX_CONCURRENT_LLM_CALLS: int = 20
    BIAS_CORRECTION_DEFAULT: float = 8.3
    SIMULATION_CACHE_TTL: int = 86400  # 24시간

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "allow",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
