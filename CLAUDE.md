# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Start

### Development Setup
```bash
# Install Python dependencies
pip install -e ".[dev]"

# Initialize database
python -m lewis_ai_system.cli init-db

# Start backend
uvicorn lewis_ai_system.main:app --host 0.0.0.0 --port 8000 --reload

# Start frontend (separate terminal)
cd frontend && npm install && npm run dev
```

### Testing
```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_full_system.py -v          # Core system tests
pytest tests/test_e2e_integration.py -v      # Integration tests
pytest tests/test_consistency_control.py -v  # Consistency tests
pytest -m "not slow"                         # Fast tests only
pytest -m "e2e"                              # E2E tests only
```

### Docker Deployment
```bash
# Full stack with all services
./start.sh

# Manual Docker Compose
docker compose up -d
```

## Architecture Overview

Lewis AI System is a **dual-mode AI orchestration platform** that provides structured workflows for both creative content generation and general task automation.

### Core Components

**Backend Stack:**
- **FastAPI** (Python 3.11+) - Async web framework with versioned API routing
- **SQLAlchemy 2.0** + AsyncPG - Async database ORM
- **Alembic** - Database migrations
- **Redis** - Caching and rate limiting
- **Weaviate** - Vector database for semantic search and memory
- **ARQ** - Background task queue for async processing
- **E2B Sandbox** - Secure Python code execution

**Frontend Stack:**
- **Next.js 14** (App Router) - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** + Radix UI - Styling
- **Zustand** - State management
- **TanStack Query** - Data fetching

### Dual-Mode Execution System

#### 1. Creative Mode (Staged Pipeline)
**Purpose:** Video generation and creative content production

**Workflow Stages:**
- **Brief** → `PlanningAgent.expand_brief()` - Expands user requirements
- **Script** → `CreativeAgent.write_script()` - Generates scene-by-scene scripts
- **Storyboard** → `CreativeAgent.split_script()` + `generate_panel_visual()` - Creates visual previews
- **Render** → Video generation via provider (Runway/Pika/Runware/Doubao)
- **Quality Control** → `QualityAgent.run_qc_workflow()` - Applies quality rules
- **Distribution** → S3 storage + preview links

**Key Files:**
- `src/lewis_ai_system/creative/workflow.py` - `CreativeOrchestrator`
- `src/lewis_ai_system/creative/repository.py` - Data persistence
- `src/lewis_ai_system/creative/models.py` - Data models
- `src/lewis_ai_system/agents/creative.py` - CreativeAgent

#### 2. General Mode (ReAct Loop)
**Purpose:** General task automation via Reasoning + Acting循环

**ReAct Loop Pattern:**
```
Question → Thought → Action → Observation → [repeat] → Final Answer
```

**Key Features:**
- Iterative execution with budget/iteration guardrails
- Vector database memory for context retention
- Automatic history compression when threshold exceeded
- Session-based state management

**Key Files:**
- `src/lewis_ai_system/general/session.py` - `GeneralModeOrchestrator`
- `src/lewis_ai_system/general/models.py` - Session data models
- `src/lewis_ai_system/agents/general.py` - GeneralAgent

### Agent System

Five specialized agents handle different aspects:

1. **PlanningAgent** (`src/lewis_ai_system/agents/planning.py`)
   - Expands and optimizes user briefs
   - Method: `expand_brief(prompt, mode)`

2. **CreativeAgent** (`src/lewis_ai_system/agents/creative.py`)
   - Script generation, storyboard creation, visual generation
   - Methods: `write_script()`, `split_script()`, `generate_panel_visual()`

3. **QualityAgent** (`src/lewis_ai_system/agents/quality.py`)
   - Quality evaluation with customizable rules engine
   - Methods: `evaluate()`, `run_qc_workflow()`, `validate_preview()`

4. **GeneralAgent** (`src/lewis_ai_system/agents/general.py`)
   - ReAct loop execution for general tasks
   - Method: `react_loop(query, tool_runtime, max_steps)`

5. **OutputFormatterAgent** (`src/lewis_ai_system/agents/output_formatter.py`)
   - Content summarization and formatting
   - Method: `summarize()`

### Tool Execution System

**Core Tools:**
- **PythonSandboxTool** - Secure Python execution via E2B
- **WebSearchTool** - Web search via Tavily API
- **WebScrapeTool** - Web content extraction via Firecrawl
- **VideoGenerationTool** - Multi-provider video generation

**Key Files:**
- `src/lewis_ai_system/tooling.py` - Tool registry and execution
- `src/lewis_ai_system/tooling/runtime.py` - Tool runtime implementation
- `src/lewis_ai_system/sandbox.py` - E2B sandbox wrapper

### API Structure

**Versioned APIs:**
- `/v1/*` - Initial API version
- `/v2/*` - Current API version with enhancements
- Legacy routes for backward compatibility

**Main Routers:**
- `src/lewis_ai_system/routers/creative.py` - Creative mode endpoints
- `src/lewis_ai_system/routers/general.py` - General mode endpoints
- `src/lewis_ai_system/routers/governance.py` - Cost monitoring and governance

### Infrastructure Services

**Docker Compose Services:**
- `lewis-api` - FastAPI application (port 8000)
- `frontend` - Next.js app (port 3000)
- `postgres` - PostgreSQL 15 (port 5432)
- `redis` - Redis 7 (port 6379)
- `weaviate` - Vector database (port 8080)
- `worker` - ARQ background task processor

## Common Development Tasks

### Database Operations
```bash
# Initialize/migrate database
python -m lewis_ai_system.cli init-db

# Seed test data
python -m lewis_ai_system.cli seed-data

# Generate new migration
alembic revision --autogenerate -m "Description"
```

### Running Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=src/lewis_ai_system --cov-report=html

# Specific test categories
pytest tests/test_creative_workflow.py -v      # Creative workflow tests
pytest tests/test_general_session.py -v        # General session tests
pytest tests/test_external_apis.py -v          # External API tests
pytest tests/test_boundary_cases.py -v         # Edge case tests
pytest -m "integration" -v                     # Integration tests
pytest -m "e2e" -v                             # End-to-end tests
```

### Code Quality
```bash
# Format code (configured in pyproject.toml)
ruff check src/
ruff format src/

# Type checking
mypy src/
```

### Local Development Scripts (Windows PowerShell)
```powershell
# One-time setup
.\scripts\setup-local-services.ps1 -CheckOnly
.\scripts\start-local.ps1 -InitDatabase

# Subsequent runs
.\scripts\start-local.ps1

# Cleanup
.\scripts\stop-local.ps1
```

## Configuration

**Environment Variables (`.env`):**
```env
# Database
DATABASE_URL=postgresql+asyncpg://lewis:lewis_pass@localhost:5432/lewis_db

# Redis
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0

# LLM Provider
LLM_PROVIDER_MODE=openrouter
OPENROUTER_API_KEY=sk-or-...

# Video Generation
VIDEO_PROVIDER=doubao  # or runway/pika/runware
DOUBAO_API_KEY=...

# General Mode Tools
E2B_API_KEY=...        # Python sandbox
TAVILY_API_KEY=...     # Web search
FIRECRAWL_API_KEY=...  # Web scraping

# Storage
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET_NAME=lewis-artifacts

# Application
SECRET_KEY=...         # Auto-generated if not set
APP_ENV=development
```

## Key Directories

```
lewis_ai_system/
├── src/lewis_ai_system/
│   ├── agents/              # All agent implementations
│   ├── creative/            # Creative mode workflow
│   │   ├── workflow.py      # CreativeOrchestrator
│   │   ├── repository.py    # Data persistence
│   │   └── models.py        # Pydantic models
│   ├── general/             # General mode workflow
│   │   ├── session.py       # GeneralModeOrchestrator
│   │   └── models.py        # Session models
│   ├── routers/             # API endpoints
│   ├── tooling.py           # Tool registry
│   ├── providers.py         # AI/LLM provider abstraction
│   ├── database.py          # Database models and connection
│   ├── config.py            # Settings and configuration
│   └── main.py              # FastAPI app entrypoint
├── frontend/                # Next.js application
├── tests/                   # Test suite (~18 test files)
├── scripts/                 # PowerShell deployment scripts
├── alembic/                 # Database migrations
└── docker-compose.yml       # Service orchestration
```

## Critical Implementation Details

### Provider Abstraction
Multiple AI providers are abstracted via `src/lewis_ai_system/providers.py`:
- **Video:** Runway, Pika, Runware, Doubao
- **LLM:** OpenRouter, OpenAI
- **Tools:** Tavily (search), Firecrawl (scraping), E2B (sandbox)

### Consistency Control
Creative mode includes a **consistency management system** ensuring visual consistency across video frames:
- `src/lewis_ai_system/creative/consistency_manager.py` - Core consistency logic
- Configurable consistency levels: `low`, `medium`, `high`
- Character and scene reference tracking

### Cost Monitoring
Real-time cost tracking across all operations:
- `src/lewis_ai_system/cost_monitor.py` - Cost monitoring
- `src/lewis_ai_system/costs.py` - Cost calculation
- Budget guardrails per session/project
- Per-tool cost estimation

### Memory Management
- **Vector Database (Weaviate)** - Semantic search and long-term memory
- **Redis Cache** - Session state and rate limiting
- **History Compression** - Automatic summarization when message threshold exceeded

### Versioning
API versioning supports backward compatibility:
- `/api/versions` endpoint lists available versions
- Version middleware tracks API evolution
- Legacy router maintains old endpoints

## Testing Strategy

**Test Categories:**
- `unit` - Single module tests
- `integration` - Multi-component tests
- `e2e` - Full workflow tests
- `slow` - Long-running tests (can be skipped with `-m "not slow"`)
- `security` - Security-related tests
- `performance` - Performance tests

**Key Test Files:**
- `test_creative_workflow.py` - Creative mode workflow tests
- `test_general_session.py` - General mode ReAct loop tests
- `test_e2e_integration.py` - End-to-end integration tests
- `test_consistency_control.py` - Creative consistency tests
- `test_external_apis.py` - External API integration tests
- `test_boundary_cases.py` - Edge case handling

## Troubleshooting

### Common Issues
1. **Database connection failed**
   - Ensure PostgreSQL is running: `net start postgresql-x64-15` (Windows)
   - Check `DATABASE_URL` in `.env`
   - Run: `python -m lewis_ai_system.cli init-db`

2. **Port already in use**
   - Backend: `netstat -ano | findstr :8000`
   - Frontend: `netstat -ano | findstr :3000`
   - Modify ports in `.env` or stop conflicting processes

3. **API keys not working**
   - Verify `.env` file is in project root
   - Check key format (no quotes/spaces)
   - Restart services after changing keys

4. **Redis connection errors**
   - Set `REDIS_ENABLED=false` in `.env` to use memory cache fallback
   - Or start Redis: `net start Redis` (Windows)

## Production Deployment

See `README.md` and `QUICKSTART.md` for detailed deployment guides. Use `./start.sh` for Docker-based deployment or PowerShell scripts in `scripts/` directory for local Windows development.

## Documentation References

- `README.md` - Comprehensive system overview with mermaid diagrams
- `QUICKSTART.md` - 5-minute setup guide for Windows
- Inline Chinese documentation throughout codebase
- API documentation available at `/docs` when running
