# syntax=docker/dockerfile:1
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Keep dependency installation in a cacheable layer. The application source is
# copied afterwards, so ordinary code edits do not reinstall dependencies.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/company-wiki-entrypoint
RUN chmod +x /usr/local/bin/company-wiki-entrypoint \
    && uv sync --locked --no-dev --no-editable

ENV WIKI_PROJECT_ROOT=/data

EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/company-wiki-entrypoint"]
CMD ["uv", "run", "--no-sync", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
