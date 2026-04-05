```
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ██╗   ██╗██████╗ ███████╗    ██████╗ ███████╗██╗   ██╗ ║
║   ██║   ██║██╔══██╗██╔════╝    ██╔══██╗██╔════╝██║   ██║ ║
║   ██║   ██║██████╔╝███████╗    ██║  ██║█████╗  ██║   ██║ ║
║   ╚██╗ ██╔╝██╔═══╝ ╚════██║    ██║  ██║██╔══╝  ╚██╗ ██╔╝ ║
║    ╚████╔╝ ██║     ███████║    ██████╔╝███████╗ ╚████╔╝  ║
║     ╚═══╝  ╚═╝     ╚══════╝    ╚═════╝ ╚══════╝  ╚═══╝   ║
║                                                          ║
║         Autonomous AI Agent for Your VPS                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
```

**Autonomous AI development agent for VPS with PARA knowledge management, spec-driven execution, and native Kimi Code CLI integration.**

## Features

- **Interactive Onboarding**: Step-by-step wizard for first-time setup with visual guides
- **PARA Knowledge Management**: Organize projects, areas, resources, and archives with semantic search
- **Spec-Driven Execution**: Define tasks in YAML specifications
- **Kimi Code CLI Integration**: Native batch execution with subscription limit management
- **Multi-Provider LLM Support**: Kimi CLI (primary), OpenAI, Anthropic, DeepSeek (fallback)
- **Security Modes**: Conservative (requires approval) and YOLO (auto-execute) modes
- **Git Integration**: Automatic backups, rollbacks, and meaningful commits
- **Validation Pipeline**: Run tests, linting, and custom validation commands
- **Batch Execution**: Process multiple tasks automatically with queue management

## Installation

```bash
# Clone repository
git clone https://github.com/username/vps-dev-agent.git
cd vps-dev-agent

# Install
pip install -e .

# Or install from PyPI (when available)
pip install vps-dev-agent
```

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ with pgvector extension
- Kimi Code CLI (optional, for native integration)

```bash
# Install Kimi CLI
curl -fsSL https://kimi.moonshot.cn/install.sh | sh

# Login to Kimi
kimi login
```

## Quick Start

### 🚀 Interactive Onboarding (Recommended)

Run the interactive wizard for first-time setup:

```bash
# Start the onboarding wizard
agent init welcome
```

This will guide you through:
1. ✅ Checking prerequisites (Python 3.11+, PostgreSQL, Git)
2. 🗄️ Configuring database connection
3. 🤖 Setting up Kimi Code CLI (optional)
4. 📁 Creating your first project
5. 📝 Generating a sample task spec

### Manual Setup

If you prefer manual configuration:

#### 1. Configure Database

```bash
# Set environment variable
export DATABASE_URL="postgresql://user:pass@localhost:5432/agent_db"

# Or use config command
agent config --database-url "postgresql://user:pass@localhost:5432/agent_db"
```

#### 2. Initialize Database

```bash
# Create tables
agent init db

# With force flag to recreate
agent init db --force
```

#### 3. Run Diagnostics

```bash
# Check all systems
agent doctor all

# Check Kimi CLI specifically
agent doctor kimi
```

#### 4. Create a Project

```bash
# Register your project
agent init project myapp --repo ./myapp

# Add areas of responsibility
agent init area myapp "Authentication" --description "User login, JWT, passwords"
agent init area myapp "API" --description "REST endpoints and schemas"
```

### 5. Create a Task Spec

Create a YAML file describing what you want to build:

```yaml
# feature.yaml
spec:
  goal: "Add user authentication feature with JWT tokens"
  
  instructions: |
    1. Create auth module in src/auth/
    2. Implement JWT token generation and validation
    3. Add middleware for protected routes
    4. Create login/logout endpoints
  
  constraints:
    - "Use existing database models (User table)"
    - "Follow existing code style and patterns"
    - "Add proper error handling"
    - "Include unit tests"
  
  expected_output: |
    - src/auth/jwt.py - JWT utilities
    - src/auth/middleware.py - Auth middleware
    - src/auth/routes.py - Login/logout endpoints
    - tests/auth/ - Unit tests
  
  security_mode: "conservative"
  
  validation:
    commands:
      - name: "Install dependencies"
        command: "pip install -e ."
        required: true
        timeout: 60
      - name: "Run tests"
        command: "pytest tests/auth/ -v"
        required: true
        timeout: 120
    require_all_pass: true
    rollback_on_failure: true
```

### 6. Add Task to Queue

```bash
# Add to queue with Kimi CLI provider
agent queue add feature.yaml --project myapp --priority 1 --provider kimi_cli
```

### 7. Execute Tasks

```bash
# Option A: Run specific task
agent run task <task-id>

# Option B: Run next pending task
agent run next

# Option C: Batch execution (process all pending tasks)
agent batch run --project myapp

# Option D: Execute spec directly
agent run spec feature.yaml --project myapp
```

### 8. Monitor Status

```bash
# Dashboard overview
agent status dashboard

# Check Kimi CLI limits
agent status limits

# Task details
agent status task <task-id>
```

## Onboarding & Welcome

The VPS Dev Agent includes an interactive onboarding wizard for first-time users.

### First Run Experience

When you run `agent init welcome`, the wizard will:

1. **Splash Screen** - Display ASCII art logo and welcome message
2. **Prerequisites Check** - Verify Python 3.11+, PostgreSQL, Git, and Kimi CLI
3. **Database Setup** - Interactive configuration with connection testing
4. **Kimi Auth** - Guide through Kimi Code CLI authentication (optional)
5. **First Project** - Create your first project (optional)
6. **Sample Spec** - Generate an example task specification
7. **Finish** - Show next steps and tips

### Re-running Onboarding

```bash
# Force re-run the wizard
agent init welcome --force

# Or using the welcome command
agent welcome start --force
```

### Brief Mode (Subsequent Runs)

For quick status after initial setup:

```bash
agent welcome brief
```

This shows:
- Minimal logo
- Queue status (pending tasks)
- Project count
- Random tip

### Visual Style

The onboarding uses a modern terminal UI inspired by GSD, Gemini CLI, and Warp:

| Color | Usage |
|-------|-------|
| Cyan | Primary accents, headers |
| Magenta | Subheaders |
| Green | Success messages, checkmarks |
| Yellow | Warnings |
| Red | Errors |
| Dim White | Secondary text |

## CLI Commands Reference

### Initialization & Onboarding

```bash
# Interactive onboarding wizard (recommended for first run)
agent init welcome [options]
  --force                   # Force re-run onboarding

# Manual initialization
agent init db [options]                    # Initialize PostgreSQL database
agent init project <name> [options]        # Register a project
agent init area <project> <name> [options] # Create an area

# Welcome commands
agent welcome start                        # Start onboarding wizard
agent welcome start --force                # Re-run onboarding
agent welcome brief                        # Show brief status (for subsequent runs)
```

### Queue Management

```bash
agent queue add <spec.yaml> [options]      # Add task to queue
  --project <name>          # Project name
  --priority <1-10>         # Task priority (lower = higher)
  --yolo                    # Enable YOLO mode
  --provider <name>         # LLM provider (kimi_cli, openai, anthropic)

agent queue list [options]                 # List tasks
  --status <status>         # Filter by status (pending, running, completed, failed)
  --project <name>          # Filter by project
  --limit <n>               # Maximum number of tasks

agent queue remove <task-id> [options]     # Remove task
  --force                   # Skip confirmation

agent queue clear [options]                # Clear tasks by status
  --status <status>         # Status to clear (default: completed)
```

### Task Execution

```bash
# Single task execution
agent run task <task-id> [options]
  --yolo                    # Auto-approve changes
  --database-url <url>      # Database URL

agent run next [options]                   # Execute next pending task

agent run spec <spec.yaml> [options]       # Execute spec directly
  --project <name>          # Project name
  --priority <n>            # Task priority

# Batch execution (recommended for multiple tasks)
agent batch run [options]
  --project <name>          # Filter by project
  --provider <name>         # LLM provider
  --mode <mode>             # Execution mode (native_batch, interactive)
  --max-tasks <n>           # Maximum tasks to execute
  --continuous              # Keep running until queue empty
  --auto-apply              # Auto-apply all changes (YOLO mode)
  --timeout <minutes>       # Timeout per task
```

### Status & Monitoring

```bash
agent status dashboard                     # System status overview
agent status projects                      # List all projects
agent status task <task-id>                # Show task details
agent status limits                        # Kimi CLI subscription limits
```

### Diagnostics

```bash
agent doctor all                           # Run all diagnostic checks
agent doctor kimi                          # Check Kimi CLI installation
agent doctor db                            # Check database connection
```

### Configuration

```bash
agent config --show                        # Show current configuration
agent config --database-url <url>          # Set database URL
```

## Kimi Code CLI Integration

The agent has native integration with Kimi Code CLI for optimal performance on VPS.

### Features

- **Batch Execution**: Process multiple tasks efficiently
- **Limit Management**: Automatically pause when near subscription limits
- **Auth Checking**: Verify Kimi CLI authentication before execution
- **Fallback Mode**: Interactive pexpect mode if batch mode unavailable

### Execution Modes

#### Native Batch Mode (Recommended)

```bash
agent batch run --mode native_batch
```

- Direct command execution
- JSON output parsing
- Fastest performance
- Best for VPS automation

#### Interactive Mode (Fallback)

```bash
agent batch run --mode interactive
```

- Uses pexpect for interactive sessions
- Handles confirmation prompts
- Useful for complex tasks requiring interaction

### Subscription Management

The agent automatically:
- Checks remaining quota before each task
- Pauses queue at 10 remaining requests (warning)
- Stops execution at 3 remaining requests (critical)
- Resumes when limits reset

```bash
# Check current limits
agent status limits
```

## Spec File Format

```yaml
spec:
  # Required: Clear description of the task
  goal: "Description of what to build"
  
  # Detailed instructions for the AI
  instructions: |
    Step-by-step instructions
    Can be multi-line
  
  # Constraints and requirements
  constraints:
    - "Constraint 1"
    - "Constraint 2"
  
  # Expected output description
  expected_output: |
    Description of expected result
  
  # PARA context references
  context:
    project_id: "uuid"              # Project reference
    area_ids: []                    # Relevant areas
    resource_ids: []                # Relevant resources
    include_archives: true          # Include past lessons
    archive_limit: 5                # Number of archives to include
  
  # Execution configuration
  execution:
    timeout_minutes: 30
    max_attempts: 3
    auto_retry: true
    parallel_tasks: false
  
  # Security mode: conservative or yolo
  security_mode: "conservative"
  
  # Validation commands
  validation:
    commands:
      - name: "Tests"
        command: "pytest tests/ -v"
        required: true
        timeout: 120
    require_all_pass: true
    rollback_on_failure: true
  
  # File context
  relevant_files:
    - "src/main.py"
    - "src/models.py"
  
  exclude_patterns:
    - "*.pyc"
    - "__pycache__/*"
  
  # LLM configuration
  model: null                       # Override default model
  temperature: 0.7                  # 0.0 - 2.0
  
  # Metadata
  metadata:
    version: "1.0.0"
    author: "developer"
    tags:
      - "feature"
      - "authentication"
```

## Security Modes

### Conservative (Default)

```yaml
spec:
  security_mode: "conservative"
```

- All shell commands require approval
- File changes outside project blocked
- Network requests restricted
- Git push requires approval
- Changes shown in diff before applying

### YOLO

```yaml
spec:
  security_mode: "yolo"
```

- Shell commands execute automatically
- File changes outside project still blocked
- Network requests allowed
- Git push still requires approval (safety)
- Changes applied immediately

Or use CLI flag:
```bash
agent queue add task.yaml --yolo
agent batch run --auto-apply
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `MOONSHOT_API_KEY` | Moonshot/Kimi API key (for adapter fallback) | No |
| `DEEPSEEK_API_KEY` | DeepSeek API key | No |
| `OPENAI_API_KEY` | OpenAI API key | No |
| `ANTHROPIC_API_KEY` | Anthropic API key | No |
| `DEFAULT_PROVIDER` | Default LLM provider | No |
| `DEFAULT_MODEL` | Default model name | No |

## Architecture

```
vps_dev_agent/
├── cli/                    # Command-line interface
│   ├── main.py            # Entry point
│   ├── commands/          # Subcommands
│   │   ├── init.py        # init db, init project, init area
│   │   ├── run.py         # run task, run spec, run next
│   │   ├── status.py      # dashboard, projects, task, limits
│   │   ├── queue.py       # add, list, remove, clear
│   │   ├── doctor.py      # diagnostic checks
│   │   ├── batch.py       # batch execution
│   │   └── welcome.py     # onboarding commands
│   └── onboarding/        # Onboarding wizard
│       ├── ascii_art.py   # Logo and visual elements
│       ├── wizard.py      # Interactive wizard
│       ├── checker.py     # Prerequisites checker
│       └── config.py      # Configuration setup
├── core/                   # Core logic
│   ├── para_models.py     # PARA database models
│   ├── spec_parser.py     # YAML spec parsing
│   ├── executor.py        # Task execution engine
│   └── trust_manager.py   # Security modes
├── bridges/               # External integrations
│   └── kimi_cli/          # Kimi Code CLI integration
│       ├── executor.py    # Batch executor
│       ├── auth.py        # Auth checker
│       ├── limit_checker.py  # Subscription limits
│       └── expect_driver.py  # Interactive mode
├── adapters/              # LLM adapters
│   └── llm_proxy.py       # LiteLLM integration
├── prompts/               # Prompt templates
│   └── formatter.py       # Prompt formatting
├── safety/                # Safety mechanisms
│   ├── git_guardian.py    # Git backup/restore
│   └── sandbox.py         # File system guards
└── utils/                 # Utilities
    └── logger.py          # Structured logging
```

## PARA Methodology

The agent uses the PARA method for knowledge management:

- **Projects**: Individual deliverables with specific goals
- **Areas**: Spheres of activity with ongoing maintenance
- **Resources**: Reference materials and knowledge base
- **Archives**: Completed tasks and lessons learned

## Best Practices

### 1. Use Onboarding Wizard for First Setup

```bash
# Run the interactive wizard instead of manual configuration
agent init welcome

# Re-run if you need to change configuration
agent init welcome --force
```

### 2. Use Batch Mode for Multiple Tasks

```bash
# Instead of running tasks one by one
agent batch run --project myapp --continuous
```

### 2. Set Appropriate Priorities

```bash
# Critical bug fix
agent queue add bugfix.yaml --priority 1

# Feature development
agent queue add feature.yaml --priority 5

# Refactoring
agent queue add refactor.yaml --priority 9
```

### 3. Use Conservative Mode for Critical Code

```yaml
spec:
  security_mode: "conservative"
  validation:
    commands:
      - name: "Tests"
        command: "pytest"
        required: true
```

### 4. Check Limits Before Long Sessions

```bash
agent status limits
agent batch run --max-tasks 10
```

### 5. Use Areas for Organization

```bash
agent init area myapp "Database" --description "Schema, migrations, queries"
agent init area myapp "API" --description "Endpoints, serializers"
agent init area myapp "Frontend" --description "Templates, static files"
```

## Troubleshooting

### Kimi CLI Not Found

```bash
# Install Kimi CLI
curl -fsSL https://kimi.moonshot.cn/install.sh | sh

# Verify installation
agent doctor kimi
```

### Authentication Issues

```bash
# Login to Kimi
kimi login

# Check status
kimi auth status

# Run diagnostic
agent doctor kimi
```

### Database Connection

```bash
# Check database
agent doctor db

# Verify PostgreSQL is running
psql $DATABASE_URL -c "SELECT 1"
```

### Limit Exceeded

```bash
# Check current limits
agent status limits

# Wait for reset or upgrade at https://kimi.moonshot.cn
```

### Onboarding Issues

```bash
# If wizard fails, check prerequisites manually
agent doctor all

# Skip wizard and configure manually
agent config --database-url <url>
agent init db

# Re-run wizard with force flag
agent init welcome --force
```

## Development

```bash
# Run tests
pytest tests/ -v

# Type checking
mypy vps_dev_agent/ --ignore-missing-imports

# Linting
flake8 vps_dev_agent/ --max-line-length=100
```

## License

MIT License

## Contributing

Contributions are welcome! Please see the repository for contribution guidelines.

## Support

- Documentation: See `docs/` directory
- Issues: GitHub Issues
- Kimi CLI: https://kimi.moonshot.cn
