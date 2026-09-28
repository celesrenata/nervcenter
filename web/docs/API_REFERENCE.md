# NerveCenter Web UI - API Reference

## Authentication

### Login

```
POST /api/auth/login
```

Request:
```json
{
  "username": "string",
  "password": "string"
}
```

Response:
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "Bearer",
  "expires_in": 1800,
  "user": {
    "username": "string",
    "roles": ["string"]
  }
}
```

### Refresh Token

```
POST /api/auth/refresh
```

Request:
```json
{
  "refresh_token": "string"
}
```

Response:
```json
{
  "access_token": "string",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

### Get Current User

```
GET /api/auth/me
```

Response:
```json
{
  "username": "string",
  "iat": "number"
}
```

## Agents

### List Agents

```
GET /api/agents
```

Response:
```json
{
  "data": [
    {
      "id": "string",
      "name": "string",
      "status": "active"
    }
  ],
  "meta": {
    "version": "string",
    "request_id": "string",
    "timestamp": "string",
    "pagination": {
      "total": "number",
      "page": "number",
      "per_page": "number"
    }
  }
}
```

### Get Agent by ID

```
GET /api/agents/{agent_id}
```

Response:
```json
{
  "id": "string",
  "name": "string",
  "status": "string"
}
```

## Goals

### List Goals

```
GET /api/goals
```

Response:
```json
{
  "data": [
    {
      "id": "string",
      "name": "string",
      "status": "active"
    }
  ],
  "meta": {
    "version": "string",
    "request_id": "string",
    "timestamp": "string",
    "pagination": {
      "total": "number",
      "page": "number",
      "per_page": "number"
    }
  }
}
```

## Tasks

### List Tasks

```
GET /api/tasks
```

Response:
```json
{
  "data": [
    {
      "id": "string",
      "name": "string",
      "status": "pending"
    }
  ],
  "meta": {
    "version": "string",
    "request_id": "string",
    "timestamp": "string",
    "pagination": {
      "total": "number",
      "page": "number",
      "per_page": "number"
    }
  }
}
```

## Systems

### Health Check

```
GET /api/health
```

Response:
```json
{
  "status": "healthy",
  "services": [
    {
      "name": "string",
      "status": "healthy",
      "version": "string",
      "message": "string",
      "checked_at": "string"
    }
  ],
  "total_services": "number",
  "healthy_services": "number"
}
```

## Incidents

### List Incidents

```
GET /api/incidents
```

Response:
```json
{
  "data": [
    {
      "id": "string",
      "title": "string",
      "severity": "critical",
      "status": "active",
      "created_at": "string",
      "updated_at": "string",
      "description": "string",
      "impact": "string",
      "tags": ["string"]
    }
  ],
  "meta": {
    "version": "string",
    "request_id": "string",
    "timestamp": "string",
    "pagination": {
      "total": "number",
      "page": "number",
      "per_page": "number"
    }
  }
}