"""Application services wired onto ``app.state.services``.

Each service here is a durable, dependency-backed component that the API
endpoint adapters read from ``app.state.services``. Services are constructed
by :mod:`backend.api.wiring` from the shared DB engine / NATS client when those
dependencies are configured, and dropped again when they are absent so the
endpoints keep their honest degradation instead of fabricating data.
"""
