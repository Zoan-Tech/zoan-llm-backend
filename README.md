# Zoan LLM Backend

A FastAPI-based backend service for handling LLM completions with PostgreSQL database integration.

## Features

- FastAPI web framework with async support
- OpenAI integration for LLM completions
- PostgreSQL database with psycopg3
- Fernet encryption for secure token handling
- Docker containerization support
- Health check endpoints

## Quick Start with Docker

### Prerequisites

- Docker and Docker Compose installed
- Copy `.env.example` to `.env` and fill in your configuration

### Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your actual values
# Required variables:
# - OPENAI_API_KEY: Your OpenAI API key
# - POSTGRES_CONN_STRING: PostgreSQL connection string
# - FERNET_SECRET: Secret key for encryption
```

### Development with Docker Compose

```bash
# Start the application
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

The application will be available at `http://localhost:8000`

**Note**: Make sure your `POSTGRES_CONN_STRING` in `.env` points to your external PostgreSQL database.

### Production Deployment

```bash
# Start production service
docker-compose -f docker-compose.prod.yml up -d --build
```

## Manual Installation (Alternative)

### Prerequisites

Install [uv](https://github.com/astral-sh/uv) - An extremely fast Python package installer and resolver:

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Verify installation
uv --version
```

### Initialize project

Using `uv` (recommended - 10-100x faster than pip):

```bash
# Create virtual environment and install dependencies
make install

# Or manually:
uv venv
uv pip install -e .
```

Traditional method (slower):

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run the application

```bash
# Using make (recommended)
make run

# Development server with auto-reload
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Production server
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

## Make Commands

```bash
make install    # Create venv and install dependencies from pyproject.toml
make run        # Run the application with uv
make sync       # Sync dependencies (creates/updates uv.lock)
make add        # Add a new package (Usage: make add PKG=package-name)
make lock       # Update uv.lock file
make all        # Install and run
```

## Docker Commands

### Build and run manually

```bash
# Build the Docker image
docker build -t zoan-llm-backend .

# Run the container
docker run -p 8000:8000 --env-file .env zoan-llm-backend
```

### Database Setup

You'll need to provide your own PostgreSQL database. Update your `.env` file with the connection string:

```bash
# Example connection string formats:
POSTGRES_CONN_STRING="postgresql://username:password@hostname:5432/database_name"
# or for external services like Supabase, Neon, etc:
POSTGRES_CONN_STRING="postgresql://username:password@host.example.com:5432/database_name?sslmode=require"
```

## API Endpoints

- `GET /api/v1/health` - Health check endpoint
- `POST /api/v1/completion` - LLM completion endpoint

## Development

### Project Structure

```
├── action/           # Business logic actions
├── api/             # API route handlers
├── client/          # HTTP client utilities
├── config/          # Configuration and templates
├── model/           # Pydantic models
├── utils/           # Helper utilities
├── main.py          # FastAPI application entry point
├── requirements.txt # Python dependencies
├── Dockerfile       # Docker configuration
└── docker-compose.yml # Development Docker setup
```

### Running Tests

```bash
# Install test dependencies (if any)
pip install pytest pytest-asyncio

# Run tests
pytest
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for LLM completions | Yes |
| `POSTGRES_CONN_STRING` | PostgreSQL connection string | Yes |
| `FERNET_SECRET` | Secret key for Fernet encryption | Yes |

## Troubleshooting

### Common Issues

1. **psycopg "no pq wrapper available" error**:
   ```bash
   pip install "psycopg[binary]"
   ```

2. **Permission denied errors in Docker**:
   ```bash
   docker-compose down && docker-compose up --build
   ```

3. **Database connection issues**:
   - Ensure your external PostgreSQL database is accessible
   - Check your `POSTGRES_CONN_STRING` format
   - Verify network connectivity to your database server
   - For cloud databases, ensure your IP is whitelisted

### Health Check

Visit `http://localhost:8000/api/v1/health` to verify the service is running.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license information here]