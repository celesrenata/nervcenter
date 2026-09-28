# NerveCenter Web UI - Features

## Overview

The NerveCenter Web UI provides a comprehensive interface for managing and monitoring your personal intelligence core.

## Core Features

### 1. Overview Dashboard

- Real-time statistics on active goals, agents, tasks, and incidents
- Quick links to manage key areas
- Recent activity summary

### 2. Systems Monitoring

- Health status of all connected systems
- System metrics and version information
- Real-time updates via WebSocket
- System-specific details

### 3. Timeline View

- Chronological event history
- Color-coded severity levels
- Event filtering capabilities
- Timeline navigation

### 4. Goals Management

- Create and track personal objectives
- Progress visualization with progress bars
- Status indicators (active, completed, pending, cancelled)
- Due date tracking

### 5. Task DAG

- Visual task dependency graph
- Task status tracking
- Priority levels
- Execution status (pending, running, completed, failed, cancelled)

### 6. Agent Monitoring

- Agent health and status
- CPU and memory usage visualization
- Task completion statistics
- Last heartbeat information

### 7. Inference Management

- Query the inference engine
- Model selection (Claude 3.5 Sonnet, Opus, Sonnet, Haiku)
- Request history
- Latency metrics

### 8. Incident Management

- Report and track incidents
- Severity levels (critical, high, medium, low)
- Status tracking (active, resolved, in-progress)
- Impact assessment
- Tag-based organization

### 9. Ask / Chat Interface

- Interactive Q&A interface
- Context-aware responses
- Quick question suggestions
- Message history

## Technical Features

### Real-time Updates

The Web UI uses WebSocket for real-time data updates, ensuring users always see the latest information.

### Authentication

- Token-based authentication
- Session management
- Role-based access control
- Secure token storage

### Dark Mode Support

All views support dark mode for reduced eye strain in low-light environments.

### Responsive Design

The UI is fully responsive and works on:
- Desktop computers
- Tablets
- Mobile devices

## Planned Features

- [ ] Advanced filtering and search
- [ ] Custom dashboard widgets
- [ ] Alert notifications
- [ ] Export functionality
- [ ] User preferences
- [ ] Multi-language support

## Performance

- Fast initial load with Vite
- Code splitting for optimized bundles
- Lazy loading of views
- Efficient WebSocket connections