# ADR-013: Vite + React + TypeScript for the frontend

Date: 2026-10-09 · Status: Accepted

## Context
The app is a dispatcher dashboard and a mobile technician page behind login.
It is client-rendered, uses Leaflet (browser-only), and has no SEO or
server-rendering needs. It is served as a static site next to a separate
Django API.

## Decision
Vite + React 19 + TypeScript with react-router-dom. Types are generated from
the backend OpenAPI schema (drf-spectacular → openapi-typescript).

## Alternatives considered
- **Next.js**: SSR/SEO gives nothing here. It needs a Node server or adapter at
  deploy time, and Leaflet needs client-only workarounds.
- **Create React App**: unmaintained.

## Trade-offs
- No SSR, so first paint waits on JS. Acceptable for an authenticated tool.
- Generated types must be regenerated whenever the API changes
  (`npm run api:types`); the diff is reviewed in the PR.
