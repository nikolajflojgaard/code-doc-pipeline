# Architecture

<!-- code-doc-pipeline:start -->

## Observed Structure

### Manifests

- `Dockerfile`
- `package.json`


### Entrypoints

- None detected


### Deployment Hints

- `Dockerfile`


### Detected Frameworks

- `Express` from `package.json`


## Diagrams

- [Context](diagrams/context.mmd)
- [Container or flow](diagrams/container-or-flow.mmd)
- [Critical sequence](diagrams/critical-sequence.mmd)
- [Data flow](diagrams/data-flow.mmd)
- [Deployment](diagrams/deployment.mmd)

## Detected Runtime Flows

- `GET /health` in `src/server.ts` -> `inline handler`; analyzer: `typescript-structured`; calls: no downstream calls detected; data: no data hints detected
- `POST /orders` in `src/server.ts` -> `inline handler`; analyzer: `typescript-structured`; calls: `acceptOrder`, `orderRepository`, `save`, `database`, `insert`; data: `repo`, `repository`, `save`, `database`


## Unknowns

- Confirm runtime boundaries with a service owner.
- Confirm whether detected interface hints are public APIs, internal routes, or framework conventions.
<!-- code-doc-pipeline:end -->
