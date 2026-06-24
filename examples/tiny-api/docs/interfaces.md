# Interfaces

<!-- code-doc-pipeline:start -->

## Detected Interface Hints

- None detected


## Detected Routes

- `GET /health` from `src/server.ts` (Express/Fastify)
- `POST /orders` from `src/server.ts` (Express/Fastify)


## Detected Runtime Flows

- `GET /health` in `src/server.ts` -> `inline handler`; calls: no downstream calls detected; data: no data hints detected
- `POST /orders` in `src/server.ts` -> `inline handler`; calls: `acceptOrder`, `orderRepository`, `save`, `database`, `insert`; data: `repo`, `repository`, `save`, `database`


## Notes

- Treat this list as a discovery aid, not a complete API contract.
- Confirm auth, schemas, request/response examples, and external consumers from code and tests.
<!-- code-doc-pipeline:end -->
