Desktop launcher facade for local backend/frontend helpers.

Phase 1 exposes process state, health checks, and restart helpers through
`/v1/desktop/launcher/*`.

Startup diagnostics inspect local prerequisites only; they do not start
helpers, register agents, or emit telemetry.
