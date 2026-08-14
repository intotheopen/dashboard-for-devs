# Vector Platform Ownership

This directory is the source of truth for vector database schema and platform-level SQL contracts.

Current schema file:
- sql/001_ito_posts_schema.sql

Why this exists:
- Keep vector data platform ownership outside the runtime backend repo.
- Let backend remain focused on online API evaluation and request-time retrieval/scoring.
- Support future split by purpose (compliance, tone, semantic/search) without overloading backend CI/CD.

Backend integration:
- The backend can load this schema directly by setting:
  - VECTOR_SCHEMA_PATH=../dashboard-for-devs/vector_platform/sql/001_ito_posts_schema.sql
- Backend fallback remains local storage/schema.sql for compatibility.

Apply manually with Docker Postgres container:

```bash
cd ../intotheopen-backend
export VECTOR_SCHEMA_PATH=../dashboard-for-devs/vector_platform/sql/001_ito_posts_schema.sql
docker exec -i intotheopen-backend-db-1 psql -U ito -d ito_posts < "$VECTOR_SCHEMA_PATH"
```

Migration strategy:
- Add new SQL files as numbered migrations.
- Keep runtime-breaking DDL backward compatible until backend rollout is complete.
- Treat this directory as platform-owned and review schema changes here first.
