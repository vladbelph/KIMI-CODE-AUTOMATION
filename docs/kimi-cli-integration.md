# Kimi CLI Integration

This document describes the integration between VPS Dev Agent and Kimi Code CLI.

## Overview

The Kimi CLI integration allows VPS Dev Agent to use Kimi Code CLI as the execution engine for development tasks. This provides a native batch execution mode as well as an interactive fallback mode.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   VPS Dev Agent │────▶│  Kimi CLI Bridge │────▶│   Kimi Code CLI │
│   (Task Queue)  │     │  (Batch/Interact)│     │   (Moonshot AI) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Components

### 1. Limit Checker

Monitors Kimi CLI subscription limits:

```bash
agent status limits
```

### 2. Auth Checker

Manages Kimi CLI authentication:

```bash
agent doctor kimi
```

### 3. Batch Executor

Main execution engine:

```bash
agent batch run --project myapp --max-tasks 10
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `agent doctor kimi` | Check Kimi CLI installation |
| `agent batch run` | Run batch execution loop |
| `agent status limits` | Show subscription limits |
| `agent queue add task.yaml --provider kimi_cli` | Add task with Kimi CLI |

## Configuration

Tasks automatically use Kimi CLI when provider is set:

```bash
agent queue add task.yaml --provider kimi_cli
```

## Safety Features

- **Limit Management**: Pause queue when near limit
- **Git Integration**: Auto-backup and rollback
- **Sandbox**: Filesystem restrictions

See full documentation in source code docstrings.
