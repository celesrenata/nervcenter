# NerveCenter Web UI

The browser-based user interface for NerveCenter - a local-first, event-driven personal intelligence core.

## Features

- 📊 **Overview Dashboard**: Get a quick snapshot of your system's current state
- 🖥️ **Systems**: Monitor and manage connected systems
- ⏱️ **Timeline**: View events and activities in chronological order
- 🎯 **Goals**: Create and track your personal objectives
- 📋 **Task DAG**: Visualize and manage task dependencies
- 🤖 **Agents**: Configure and monitor AI agents
- 🧠 **Inference**: Track inference requests and responses
- ⚠️ **Incidents**: Monitor and manage system incidents
- 💬 **Ask**: Interactive Q&A interface

## Tech Stack

### Mock Mode

When `VITE_API_BASE` is unset, the UI runs in mock mode using representative fixtures. This allows standalone testing without a live backend.

### API Contract

The UI expects the backend API to follow the contract defined in `docs/nervcenter-spec.md` §46. If the API doesn't fully match the contract, gaps are documented in `CONTRACT_GAPS.md`.

- **React 18** with TypeScript
- **Vite** for fast development and optimized builds
- **Tailwind CSS** for styling
- **Axios** for API communication
- **React Router** for navigation

## Getting Started

### Prerequisites

- Node.js 18+ 
- Python 3.11+
- NerveCenter backend running

### Installation

```bash
cd web
npm install
```

### Development

```bash
npm run dev
```

The UI will be available at `http://localhost:3000`

### Build for Production

```bash
npm run build
```

## Configuration

The UI connects to the backend API at `http://localhost:8000` by default. To change this, modify the proxy configuration in `vite.config.ts`.

## Authentication

Default credentials:
- Username: `admin`
- Password: `password`

## Development

### Folder Structure

```
web/
├── src/
│   ├── api/          # API client and WebSocket client
│   ├── auth/         # Authentication context
│   ├── components/   # Reusable components
│   ├── hooks/        # Custom React hooks
│   ├── views/        # Page components
│   ├── docs/         # Documentation files
│   └── index.css     # Global styles
├── index.html
├── vite.config.ts
└── package.json
```

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Deployment

The Web UI is deployed to AWS EKS via the HelloDJ deployment pipeline. See the `deployments/` directory for Kubernetes manifests.

## Contributing

1. Create a feature branch
2. Make your changes
3. Run `npm run lint` to ensure code quality
4. Submit a pull request

## License

MIT