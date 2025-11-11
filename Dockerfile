# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Set work directory
WORKDIR /app

# Install system dependencies and uv
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        graphviz \
        libgraphviz-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy pyproject.toml first to leverage Docker cache
COPY pyproject.toml .

# Install Python dependencies using uv (much faster than pip)
RUN uv pip install --system -e .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser

# Create necessary directories with proper permissions as root
RUN mkdir -p /app/games /app/data

# Copy project files and set ownership
COPY --chown=appuser:appuser . .

# Set proper permissions for all directories and files
RUN chown -R appuser:appuser /app \
    && chmod -R 755 /app \
    && chmod -R 775 /app/games /app/data

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
