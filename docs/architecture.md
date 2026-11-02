# Architecture

Each node owns one SQLite database. The FastAPI app factory creates the
repository, routers, metrics registry, rate limiter, and background peer
synchronizer. Local writes append an immutable operation and update the
materialized inventory in the same transaction.

```mermaid
flowchart LR
  UI[Dashboard] --> API[FastAPI node]
  API --> REPO[Repository]
  REPO --> LOG[SQLite operation log]
  REPO --> VIEW[Entity projection]
  SYNC[Async peer sync] <--> API
  SYNC --> DIGEST[Version vector and range digests]
  REPO --> GRAPH[Causal and topology analysis]
  SIM[Seeded simulator] --> MERGE[Pure merge rules]
  REPO --> MERGE
```

The project also contains optional local NLP duplicate suggestions and vision
helpers. Install them with the `[nlp]` and `[vision]` extras respectively.
