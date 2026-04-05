# Kimi CLI Integration

This document describes the integration between VPS Dev Agent and Kimi Code CLI.

## Overview

The Kimi CLI integration allows VPS Dev Agent to use Kimi Code CLI as the execution engine for development tasks. This provides a native batch execution mode as well as an interactive fallback mode.

> 💡 **Quick Setup**: Run `agent init welcome` for interactive onboarding that will check and configure Kimi CLI automatically.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   VPS Dev Agent │────▶│  Kimi CLI Bridge │────▶│   Kimi Code CLI │
│   (Task Queue)  │     │  (Batch/Interact)│     │   (Moonshot AI) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Onboarding Integration

The onboarding wizard (`agent init welcome`) now includes automated Kimi CLI setup:

### Prerequisites Check (Step 2)

Automatically detects Kimi CLI installation:

```
✓ Python 3.11+         PASS    3.11.4
✓ PostgreSQL           PASS    14.5
✓ Git                  PASS    2.34.1
! Kimi Code CLI        WARN    Not installed (optional)
```

If Kimi CLI is not installed, the wizard will show:
- Installation hint: `curl -fsSL https://kimi.moonshot.cn/install.sh | sh`
- Download link: https://kimi.moonshot.cn/download
- Continue option (Kimi CLI is optional)

### Kimi Auth Setup (Step 4)

If Kimi CLI is installed but not authenticated, the wizard will:

1. **Detect authentication status** via `KimiAuthChecker`
2. **Show instructions**:
   ```
   Kimi CLI detected but not authenticated
   
   Instructions:
   1. Visit: https://kimi.moonshot.cn/auth/device
   2. Or run: kimi login
   ```
3. **Auto-launch** `kimi login` in background
4. **Wait with spinner** for up to 60 seconds
5. **Confirm authentication** before continuing

This eliminates manual setup steps for new users.

## Components

### 1. Limit Checker (`vps_dev_agent.bridges.kimi_cli.limit_checker`)

Monitors Kimi CLI subscription limits and manages quota:

```python
from vps_dev_agent.bridges.kimi_cli import LimitChecker, LimitManager

# Check remaining quota
checker = LimitChecker()
quota = checker.get_remaining_quota()

print(f"Remaining requests: {quota.requests_remaining}")
print(f"Tier: {quota.tier}")
print(f"Near limit: {quota.is_near_limit}")
print(f"Critical: {quota.is_critical}")

# Manage queue based on limits
manager = LimitManager(checker)
can_proceed, message = manager.should_pause_queue()
```

**CLI Commands:**

```bash
# Check subscription limits
agent status limits

# Example output:
# Metric              Value
# ─────────────────────────────
# Tier                Pro
# Requests Remaining  95
# Tokens Remaining    50000
```

**Automatic Actions:**
- Check limits before every task
- Pause queue at 10 remaining requests (warning threshold)
- Stop execution at 3 remaining requests (critical threshold)
- Auto-resume when limits reset

### 2. Auth Checker (`vps_dev_agent.bridges.kimi_cli.auth`)

Manages Kimi CLI authentication:

```python
from vps_dev_agent.bridges.kimi_cli import KimiAuthChecker

auth = KimiAuthChecker()

# Check if authenticated
if auth.is_session_valid():
    print("Authenticated!")
else:
    print("Please run: kimi login")

# Get full status
status = auth.get_installation_status()
print(f"Installed: {status['installed']}")
print(f"Version: {status['version']}")
print(f"Authenticated: {status['authenticated']}")
```

**CLI Commands:**

```bash
# Check Kimi CLI installation and auth
agent doctor kimi

# Example output:
# ✓ Installed          PASS    kimi version 1.2.3
# ✓ Authenticated      PASS    user@example.com
# ✓ Subscription       Pro     95 requests remaining
```

**Onboarding Integration:**

The onboarding wizard (`agent init welcome`) automatically:
1. Detects if Kimi CLI is installed
2. Checks authentication status
3. Guides through authentication if needed
4. Waits for auth completion with spinner

### 3. Batch Executor (`vps_dev_agent.bridges.kimi_cli.executor`)

Main execution engine with two modes:

#### Native Batch Mode (Recommended)

```python
from vps_dev_agent.bridges.kimi_cli import KimiBatchExecutor, ExecutionMode

executor = KimiBatchExecutor(
    database_url="postgresql://localhost/agent_db",
    mode=ExecutionMode.NATIVE_BATCH,
    auto_apply=False,  # Set True for YOLO mode
    timeout_minutes=30,
)

# Run batch loop
results = executor.run_batch_loop(
    project_name="myapp",
    max_tasks=10,
    continuous=True,  # Keep running until queue empty
)
```

**CLI Commands:**

```bash
# Run batch execution
agent batch run --project myapp --mode native_batch

# With options
agent batch run \
    --project myapp \
    --max-tasks 10 \
    --continuous \
    --auto-apply
```

#### Interactive Mode (Fallback)

Uses pexpect for interactive sessions when native batch is unavailable:

```python
from vps_dev_agent.bridges.kimi_cli.expect_driver import KimiExpectDriver

driver = KimiExpectDriver(timeout=300)

result = driver.execute_task(
    prompt_text="Create a Python function...",
    auto_apply=True,  # Auto-confirm changes
    working_dir="/path/to/project",
)

print(f"Exit code: {result.exit_code}")
print(f"Files modified: {result.files_modified}")
print(f"Summary: {result.summary}")
```

**CLI Commands:**

```bash
# Use interactive mode
agent batch run --mode interactive
```

### 4. Prompt Formatter (`vps_dev_agent.prompts.formatter`)

Formats prompts specifically for Kimi CLI:

```python
from vps_dev_agent.prompts.formatter import PromptFormatter

formatter = PromptFormatter()

prompt = formatter.format_kimi_prompt(
    task=task_obj,
    project=project_obj,
    spec=spec_obj,
    context=para_context,
    auto_apply=False,
)
```

**Prompt Template Structure:**

```
# Task ID: {task_id}
# Project: {project_name}
# Provider: Kimi Code CLI

## Goal
{goal}

## Instructions
{instructions}

## Constraints
- Constraint 1
- Constraint 2

## Context (from PARA)
{areas, resources, archives}

---
Mode: Execute task and {apply_confirmation}
```

## Setup Workflow (New Users)

For first-time setup, use the onboarding wizard:

```bash
agent init welcome
```

This automated workflow will:

1. **Prerequisites Check**
   - Verify Python 3.11+, PostgreSQL, Git
   - Detect Kimi CLI installation
   - Show installation instructions if missing

2. **Database Setup**
   - Configure PostgreSQL connection
   - Test connectivity
   - Save configuration

3. **Kimi CLI Setup**
   - Check if Kimi CLI is installed
   - Verify authentication status
   - Guide through authentication if needed
   - Wait for auth completion

4. **First Project** (optional)
   - Create initial project
   - Generate sample task spec

## Task Execution Flow

For each task execution, the following happens:

1. **Pre-flight Checks**
   - Verify Kimi CLI installation
   - Check authentication status
   - Verify subscription limits (via `LimitChecker`)

2. **Git Backup**
   - Create backup branch: `auto/backup/{task_id}`
   - Stash uncommitted changes

3. **Prompt Preparation**
   - Load spec from YAML
   - Build PARA context (Projects, Areas, Resources, Archives)
   - Format prompt for Kimi CLI

4. **Execution**
   - **Native Batch**: Execute via `kimi execute` command
   - **Interactive**: Use pexpect wrapper

5. **Result Parsing**
   - Parse JSON output
   - Extract files_modified, summary, tokens_used

6. **Validation**
   - Run spec validation commands
   - Check exit codes

7. **Finalization**
   - On success: Git commit with summary
   - On failure: Git rollback
   - Update task status and metadata

## Configuration

### Environment Variables

```bash
# Database (required)
export DATABASE_URL="postgresql://user:pass@localhost/agent_db"

# Optional: Default provider
export DEFAULT_PROVIDER="kimi_cli"
```

### Task Provider Selection

When adding tasks to the queue:

```bash
# Use Kimi CLI (default)
agent queue add task.yaml --provider kimi_cli

# Use other providers (fallback to generic LLM adapter)
agent queue add task.yaml --provider openai
```

Or in the spec file:

```yaml
spec:
  llm_provider:
    type: "kimi_cli"
    mode: "batch"  # or "interactive"
    auto_apply: false
    context_depth: "standard"  # standard, extended, max
```

## CLI Commands Reference

### Setup & Configuration

| Command | Description |
|---------|-------------|
| `agent init welcome` | **Recommended**: Interactive onboarding with Kimi CLI setup |
| `agent init welcome --force` | Re-run onboarding (e.g., to reconfigure Kimi) |
| `agent doctor kimi` | Check Kimi CLI installation and auth |
| `agent doctor all` | Run all diagnostic checks |

### Execution

| Command | Description |
|---------|-------------|
| `agent batch run` | Run batch execution loop |
| `agent batch run --mode interactive` | Use interactive mode |
| `agent status limits` | Show subscription limits |
| `agent queue add task.yaml --provider kimi_cli` | Add task with Kimi CLI |

## Safety Features

### Limit Management

- **Check Frequency**: Before every task
- **Warning Threshold**: 10 remaining requests
- **Critical Threshold**: 3 remaining requests
- **Auto-pause**: Queue stops when limits reached
- **Auto-resume**: Polls for limit reset every hour

### Git Integration

- **Automatic Backup**: Before each task execution
- **Rollback on Failure**: Restores original state
- **Commit on Success**: Meaningful commit messages from spec
- **Cleanup**: Removes backup branches after success

### Sandbox

- **Path Restrictions**: No writes outside project
- **Dangerous Paths**: Blocks /etc, ~/.ssh, /root
- **Path Traversal**: Prevents `../` attacks

## Error Handling

### Retry Logic

```python
# Syntax errors: Auto-retry
if exit_code == 1 and "SyntaxError" in stderr:
    retry_task()

# Validation failed: Archive lesson
if "tests failed" in output:
    archive_lesson()

# Limit reached: Pause queue
if "limit exceeded" in output:
    pause_queue()
```

### Partial Success

- **Exit code 2** or "Continue?" prompt
- **YOLO mode**: Auto-accept
- **Conservative mode**: Pause for review

## Troubleshooting

### Quick Fix with Onboarding

Most Kimi CLI issues can be resolved with the onboarding wizard:

```bash
# Re-run onboarding to reconfigure Kimi CLI
agent init welcome --force
```

This will:
- Re-check prerequisites
- Verify/reconfigure authentication
- Test connectivity

### Kimi CLI Not Found

```bash
# Option 1: Use onboarding wizard (recommended)
agent init welcome

# Option 2: Manual installation
curl -fsSL https://kimi.moonshot.cn/install.sh | sh

# Or visit: https://kimi.moonshot.cn/download

# Verify installation
agent doctor kimi
```

### Authentication Issues

```bash
# Option 1: Use onboarding wizard (recommended)
agent init welcome --force

# Option 2: Manual authentication
kimi login

# Check status
kimi auth status

# Run diagnostic
agent doctor kimi
```

### Limit Exceeded

```bash
# Check current limits
agent status limits

# Wait for reset or upgrade at https://kimi.moonshot.cn
```

### Connection Issues

```bash
# Test database connection
agent doctor db

# Check Kimi CLI connectivity
kimi --version
```

## Migration from Generic LLM Adapter

To migrate existing tasks to use Kimi CLI:

```bash
# Update pending tasks
agent queue list --status pending

# For each task, you can re-add with kimi_cli provider
agent queue add task.yaml --provider kimi_cli
```

Or update in database:

```sql
UPDATE tasks 
SET llm_provider = 'kimi_cli' 
WHERE status = 'pending';
```

## Performance Considerations

### Batch Mode vs Interactive Mode

| Mode | Speed | Use Case |
|------|-------|----------|
| Native Batch | Fastest | VPS automation, CI/CD |
| Interactive | Slower | Complex prompts, debugging |

### Context Size

| Depth | Tokens | Use Case |
|-------|--------|----------|
| Standard | ~2000 | Simple tasks |
| Extended | ~4000 | Medium complexity |
| Max | ~8000 | Complex multi-file changes |

Set in spec:

```yaml
spec:
  context_depth: "extended"
```

## API Reference

See module docstrings for detailed API documentation:

- `vps_dev_agent.bridges.kimi_cli.executor` - Batch execution
- `vps_dev_agent.bridges.kimi_cli.limit_checker` - Quota management
- `vps_dev_agent.bridges.kimi_cli.auth` - Authentication
- `vps_dev_agent.bridges.kimi_cli.expect_driver` - Interactive mode

## Related Documentation

- [Main README](../README.md) - Quick start and overview
- [Onboarding Guide](../README.md#onboarding--welcome) - First-time setup with automated Kimi CLI configuration

## Summary

The Kimi CLI integration is now seamlessly integrated with the onboarding experience:

- **New users**: Run `agent init welcome` for automated setup
- **Existing users**: Run `agent init welcome --force` to reconfigure
- **Diagnostics**: Use `agent doctor kimi` for troubleshooting
- **Daily use**: `agent batch run` for task execution

The onboarding wizard eliminates manual configuration steps and provides a smooth first-time experience with Kimi Code CLI integration.
