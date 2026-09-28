# NerveCenter Web UI - Developer Guide

## Overview

This document provides a detailed guide for developers working on the NerveCenter Web UI.

## Architecture

The Web UI is built using:

- **React 18** with TypeScript for type safety
- **Vite** as the build tool for fast development and optimized builds
- **Tailwind CSS** for styling
- **React Router** for client-side routing
- **Axios** for API communication
- **WebSocket** for real-time updates

## Project Structure

```
web/
├── src/
│   ├── api/              # API client and WebSocket client
│   │   ├── client.ts     # REST API client with Axios
│   │   └── WebSocketClient.ts
│   ├── auth/             # Authentication context and hooks
│   │   └── AuthContext.tsx
│   ├── components/       # Reusable components
│   │   ├── Layout.tsx
│   │   └── RequireAuth.tsx
│   ├── hooks/            # Custom React hooks
│   │   └── useRealtimeUpdates.ts
│   ├── views/            # Page components
│   │   ├── OverviewView.tsx
│   │   ├── SystemsView.tsx
│   │   ├── TimelineView.tsx
│   │   ├── GoalsView.tsx
│   │   ├── TaskDagView.tsx
│   │   ├── AgentsView.tsx
│   │   ├── InferenceView.tsx
│   │   ├── IncidentsView.tsx
│   │   └── AskView.tsx
│   │   └── LoginView.tsx
│   ├── App.tsx           # Main application component
│   ├── main.tsx          # Application entry point
│   └── index.css         # Global styles with Tailwind
├── public/               # Static assets
├── index.html            # HTML entry point
├── vite.config.ts        # Vite configuration
├── tailwind.config.js    # Tailwind configuration
├── postcss.config.js     # PostCSS configuration
├── tsconfig.json         # TypeScript configuration
└── package.json          # NPM dependencies and scripts
```

## Development

### Starting Development Server

```bash
cd web
npm run dev
```

The development server will start on `http://localhost:3000`.

### Available Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Start development server with HMR |
| `npm run build` | Build for production |
| `npm run preview` | Preview production build locally |
| `npm run lint` | Run ESLint |

## API Integration

### REST API

The Web UI communicates with the NerveCenter backend at `/api` through the API client in [`src/api/client.ts`](src/api/client.ts).

```typescript
import { api, agentsApi, goalsApi } from './api/client'

// Get all agents
const response = await agentsApi.list()

// Get specific goal
const goal = await goalsApi.get('goal-123')
```

### WebSocket for Real-time Updates

Use the `useRealtimeUpdates` hook to subscribe to WebSocket events:

```typescript
import { useRealtimeUpdates } from '../hooks/useRealtimeUpdates'

const { data, loading, error, ws } = useRealtimeUpdates(
  'ws://localhost:8000/ws',
  initialData
)
```

## Authentication

Authentication is handled by the [`AuthContext`](src/auth/AuthContext.tsx). Protected routes use the `RequireAuth` component.

```typescript
<Route
  path="/"
  element={<Layout />}
>
  <Route element={<RequireAuth />}>
    <Route path="/" element={<OverviewView />} />
  </Route>
</Route>
```

### Login Flow

1. User navigates to `/login`
2. Credentials are sent to `/api/auth/login`
3. Access token is stored in `localStorage`
4. User is redirected to `/`

## Styling

The project uses Tailwind CSS for utility-first styling. Dark mode is supported with the `dark:` variant.

```jsx
<div className="bg-white dark:bg-gray-800 p-6 rounded-lg shadow-lg">
  <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
    Title
  </h1>
</div>
```

## Deployment

The Web UI is deployed to AWS EKS via the HelloDJ deployment pipeline.

### Deployment Process

1. Build the application: `npm run build`
2. The built files are in the `dist/` directory
3. Deploy to Kubernetes using the manifests in `deployments/`

## Testing

Unit tests can be added using React Testing Library:

```bash
npm install --save-dev @testing-library/react @testing-library/jest-dom
```

## Troubleshooting

### Common Issues

1. **API Connection Issues**: Ensure the backend is running at `http://localhost:8000`

2. **CORS Errors**: The backend has CORS enabled for development

3. **WebSocket Connection Failed**: Verify the WebSocket endpoint is available at `/ws`

## Contributing

1. Create a feature branch from `main`
2. Make your changes
3. Run `npm run build` to verify
4. Submit a pull request