# API Contract Gaps

## Overview

This document tracks gaps between the NerveCenter Web UI and the backend API contract. These gaps block certain views or functionality when running in live mode.

## Current Gaps

1. **Inference View**:
   - Missing `/models/history` endpoint for historical performance data
   - `/compute` endpoint doesn't include `fallbacks24h` field

2. **Task DAG View**:
   - `/tasks` endpoint doesn't include `estimatedDuration` field

3. **Ask View**:
   - `/ask` endpoint doesn't support provenance in response

## Resolution Status

- [ ] Backend team to implement missing endpoints
- [ ] Web UI to handle missing fields gracefully

## Testing

When testing with live API, these gaps will be logged to the browser console and displayed in the UI.
