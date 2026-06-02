# IFRS Agent Dockerfile
# Python 3.11 기반 이미지 사용
FROM python:3.11-slim

# 메타데이터
LABEL maintainer="IFRS Agent Team"
LABEL description="IFRS 지속가능성 공시 보고서 생성 에이전트"
LABEL version="1.0.0"

# 환경 변수 설정
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    postgresql-client \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 비root 사용자 생성 (보안)
RUN useradd -m -u 1000 ifrsagent && \
    mkdir -p /app /app/data /app/logs && \
    chown -R ifrsagent:ifrsagent /app

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치 (캐싱 최적화)
COPY requirement.txt /app/requirement.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirement.txt

# 프로젝트 파일 복사
COPY --chown=ifrsagent:ifrsagent . /app/

# 비root 사용자로 전환
USER ifrsagent

# 포트 노출 (필요시)
# EXPOSE 8000

# 헬스체크 (선택적)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD python -c "from ifrs_agent.config.settings import get_settings; get_settings(); import sys; sys.exit(0)"

# 기본 명령어 (main.py 실행)
# 환경 변수는 docker run 시 -e 옵션으로 전달하거나 docker-compose.yml에서 설정
CMD ["python", "main.py"]

