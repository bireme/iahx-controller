########### BASE STAGE ###########
FROM python:3.14-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install uv package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

EXPOSE 8000

########### DEV STAGE ###########
FROM base AS dev

# Install dependencies
COPY pyproject.toml uv.lock .
RUN uv sync

# Set app directory
WORKDIR app/

CMD uv run fastapi dev app.py --host 0.0.0.0

########### PRODUCTION STAGE ###########
FROM base AS prod

# Install dependencies
COPY pyproject.toml uv.lock .
RUN uv sync --no-dev

# Set app directory
WORKDIR app/

# Copy src files
COPY ./controller /app/

COPY ./redis_data /redis_data/

# Execute app
CMD uv run --no-dev uvicorn app:app --host 0.0.0.0 --port 8000 ${APP_RUN_PARAMS}
