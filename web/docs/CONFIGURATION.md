# NerveCenter Web UI - Configuration Guide

## Configuration Overview

The Web UI uses several configuration files for different purposes.

## Vite Configuration

The [`vite.config.ts`](../vite.config.ts) file configures the Vite development server and build process.

### Key Settings

- **Port**: 3000
- **Proxy**: `/api` → `http://localhost:8000`
- **Alias**: `@` → `./src`

### Example Configuration

```typescript
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

## TypeScript Configuration

The [`tsconfig.json`](../tsconfig.json) file configures TypeScript compilation.

### Key Settings

- **Target**: ES2020
- **Module**: ESNext
- **JSX**: react-jsx
- **Module Resolution**: bundler

## Tailwind CSS Configuration

The [`tailwind.config.js`](../tailwind.config.js) file configures Tailwind CSS.

### Default Configuration

```javascript
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

## Environment Variables

Currently, the Web UI does not use environment variables. All configuration is done in the respective config files.

## Customizing the Build

### Changing the Port

Edit [`vite.config.ts`](../vite.config.ts):

```typescript
server: {
  port: 3001, // Change to desired port
}
```

### Adding Proxy Rules

Add to the `proxy` section in [`vite.config.ts`](../vite.config.ts):

```typescript
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://localhost:8000',
    changeOrigin: true,
    ws: true,
  },
},
```

### Enabling HTTPS for Development

```typescript
server: {
  https: true,
}