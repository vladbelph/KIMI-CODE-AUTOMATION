# VPS Dev Agent

Autonomous AI development agent for VPS with PARA knowledge management and spec-driven execution.

## Features

- **PARA Knowledge Management**: Organize projects, areas, resources, and archives
- **Spec-Driven Execution**: Define tasks in YAML specifications
- **Security Modes**: Conservative (requires approval) and YOLO (auto-execute) modes
- **Git Integration**: Automatic backups and rollbacks
- **Multi-Provider LLM Support**: Works with Moonshot (Kimi), DeepSeek, OpenAI, Anthropic
- **Validation Pipeline**: Run tests, linting, and custom validation commands

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

## Quick Start

### 1. Configure Database

```bash
# Set environment variable
export DATABASE_URL="postgresql://user:pass@localhost:5432/agent_db"

# Or use config command
agent config --database-url "postgresql://user:pass@localhost:5432/agent_db"
```

### 2. Initialize Database

```bash
# Create tables
agent init db

# With force flag to recreate
agent init db --force
```

### 3. Create a Project

```bash
# Register your project
agent init project myapp --repo ./myapp

# Add areas of responsibility
agent init area myapp "Authentication" --description "User login, JWT, passwords"
agent init area myapp "API" --description "REST endpoints and schemas"
```

### 4. Create a Task Spec

Create a YAML file describing what you want to build:

```yaml
# feature.yaml
spec:
  goal: "Add user login endpoint with JWT"
  instructions: |
    1. Create auth module
    2. Implement JWT token generation
    3. Add login endpoint
  security_mode: "conservative"
  validation:
    commands:
      - name: "Tests"
        command: "pytest tests/ -v"
        required: true
```

### 5. Add Task to Queue

```bash
# Add to queue
agent queue add feature.yaml --project myapp --priority 1
```

### 6. Execute Task

```bash
# Run in conservative mode (with confirmations)
agent run task <task-id>

# Or run next pending task
agent run next

# YOLO mode (auto-approve)
agent run task <task-id> --yolo
```

## CLI Commands

### Initialization

```bash
agent init db                    # Initialize database
agent init project <name>        # Register a project
agent init area <project> <name> # Create an area
```

### Queue Management

```bash
agent queue add <spec.yaml>      # Add task to queue
agent queue list                 # List tasks
agent queue list --status failed # Filter by status
agent queue remove <task-id>     # Remove task
agent queue clear --status completed  # Clear completed tasks
```

### Task Execution

```bash
agent run task <task-id>         # Execute specific task
agent run next                   # Execute next pending task
agent run spec <spec.yaml>       # Execute spec directly
```

### Status

```bash
agent status dashboard           # Show system status
agent status projects            # List projects
agent status task <task-id>      # Show task details
```

### Configuration

```bash
agent config --show              # Show configuration
agent config --database-url <url> # Set database URL
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `MOONSHOT_API_KEY` | Moonshot/Kimi API key |
| `DEEPSEEK_API_KEY` | DeepSeek API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `ANTHROPIC_API_KEY` | Anthropic API key |

## Spec File Format

```yaml
spec:
  goal: "Description of what to build"
  instructions: |
    Step-by-step instructions for the AI
  constraints:
    - "Constraint 1"
    - "Constraint 2"
  expected_output: |
    Description of expected result
  
  context:
    project_id: "uuid"          # Project reference
    area_ids: []                # Relevant areas
    include_archives: true      # Include past lessons
    archive_limit: 5
  
  execution:
    timeout_minutes: 30
    max_attempts: 3
    auto_retry: true
  
  security_mode: "conservative"  # or "yolo"
  
  validation:
    commands:
      - name: "Tests"
        command: "pytest"
        required: true
        timeout: 120
    require_all_pass: true
    rollback_on_failure: true
  
  relevant_files:
    - "src/main.py"
    - "src/models.py"
```

## Security Modes

### Conservative (Default)
- All shell commands require approval
- File changes outside project blocked
- Network requests restricted
- Git push requires approval

### YOLO
- Shell commands execute automatically
- File changes outside project still blocked
- Network requests allowed
- Git push still requires approval (safety)

## Architecture

```
vps_dev_agent/
├── cli/              # Command-line interface
│   ├── main.py       # Entry point
│   └── commands/     # Subcommands
├── core/             # Core logic
│   ├── para_models.py    # PARA database models
│   ├── spec_parser.py    # YAML spec parsing
│   ├── executor.py       # Task execution
│   └── trust_manager.py  # Security modes
├── adapters/         # External integrations
│   └── llm_proxy.py  # LiteLLM integration
├── safety/           # Safety mechanisms
│   ├── git_guardian.py   # Git backup/restore
│   └── sandbox.py        # File system guards
└── utils/            # Utilities
    └── logger.py         # Structured logging
```

## License

MIT License
