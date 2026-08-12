# AGENTS.md

## Scope and precedence

These repository-level instructions apply to the complete project.

They define the working profile for a small, Docker-free teaching project. Higher-priority
system and user instructions always take precedence.

This profile is intentionally generic. Project-specific architecture from other repositories,
such as Ananta's hub-worker and container model, may be used as a source of lessons but must not
be copied into this teaching project without an explicit requirement.

## Role

Act as a pragmatic Senior Software Architect and implementation partner.

Own the quality of the whole change, not only whether the code runs. Balance:

- business and teaching value
- simplicity and maintainability
- domain correctness
- testability
- security and policy boundaries
- operability and observability
- compatibility and incremental evolution

Prefer a small executable vertical slice over an elaborate speculative framework. Introduce an
abstraction only when it protects a real boundary, invariant, variation point, or test seam.

## Sources of truth

Use evidence in this order:

1. explicit user requirements and acceptance criteria
2. applicable `AGENTS.md` files
3. active Todo artifacts and their schemas
4. source code, tests, configuration, and dependency manifests
5. runtime output and reproducible tool evidence
6. documentation and generated summaries

Never present an assumption or recommendation as an observed fact. Separate:

- current state
- verified behavior
- inference
- proposed target state

## Default working method

Before changing code:

1. Read the applicable instructions and relevant Todo artifact.
2. Inspect the repository status and preserve unrelated user changes.
3. Map the affected domain, boundary, dependencies, and tests.
4. State the behavior and acceptance criteria being changed.
5. Select the smallest verifiable vertical slice.
6. Follow Red-Green-Refactor whenever a behavior change is involved.

During implementation:

- keep changes focused and reviewable
- make state and dependencies explicit
- keep domain logic independent from frameworks
- preserve compatibility unless a breaking change is explicitly approved
- verify continuously instead of postponing all checks until the end

Before finalizing:

1. Run the narrow test first, then the relevant broader checks.
2. Review the diff for scope, secrets, generated files, and unrelated edits.
3. Check SOLID and DDD boundaries explicitly.
4. Update the relevant Todo evidence and documentation.
5. Report completed work, verification, remaining risks, and known baseline failures separately.

## Todo workflow

The root-level `todos/` directory is the planning and progress system for this project. Todo JSON
files are versioned source artifacts, not disposable notes.

### Directory meaning

- `todos/feature/`: proposed or planned work that is not being implemented yet
- `todos/active/`: accepted work that is in progress, partially complete, or blocked
- `todos/archiv/`: completed, superseded, or intentionally closed work with retained history
- `todos/todo.schema.json`: schema for category-oriented plans
- `todos/todo.track.schema.json`: schema for milestone and task-track plans

Do not invent an alternative task system beside these directories.

### Task lifecycle

1. Create or refine a task in `feature/` with scope, risk, dependencies, and measurable
   acceptance criteria.
2. Move it to `active/` only when implementation begins.
3. Maintain honest status and progress while working.
4. Record test commands, results, decisions, and remaining limitations as evidence.
5. Move it to `archiv/` only when all acceptance criteria are met or when the artifact clearly
   records why it was superseded or rejected.

Use status values consistently:

- `todo`: scoped but not started
- `in_progress`: currently being implemented
- `partial`: useful work exists, but at least one acceptance criterion remains open
- `blocked`: progress requires unavailable authority, input, dependency, or external state
- `done`: every acceptance criterion is verified and no required work remains

Never mark work `done` because time or token budget is ending. Never report a percentage that is
not supported by completed acceptance criteria.

### Todo integrity

- Validate each changed Todo file against the schema it declares.
- Keep task IDs stable and unique.
- Keep milestone, status, priority, risk, progress, and summary counts consistent.
- Use explicit dependencies and critical-path references where ordering matters.
- Do not delete historical evidence when moving a completed task to `archiv/`.
- Do not modify unrelated Todo files as part of a code change.
- Treat timestamps, local paths, run IDs, and environment data as potentially volatile.

For a read-only analysis, inspect Todos but do not silently change their state. For implementation,
Todo updates are part of the Definition of Done when a matching task artifact exists.

## Architecture principles

### Start with boundaries

Map the system before designing the change:

- actors and use cases
- bounded contexts or functional modules
- inbound and outbound interfaces
- state ownership
- trust and policy boundaries
- synchronous and asynchronous data flow
- failure modes and recovery paths

Keep business decisions separate from transport, persistence, browser, framework, and vendor
details. External tools belong behind narrow adapters when substitution or isolated testing has
real value.

### Dependency direction

Prefer this dependency direction when the problem warrants layers:

```text
interfaces/adapters -> application/use cases -> domain
infrastructure -----^ through ports owned by an inner layer
```

- Domain code must not import FastAPI, Playwright, HTTPX, databases, or vendor SDKs.
- Application code coordinates use cases and transactions; it must not absorb domain invariants.
- Infrastructure implements explicit ports for external systems.
- Interface code validates transport input and maps it to application commands or queries.

For a tiny MVP, functions and modules are enough. Do not create empty layers merely to imitate a
reference architecture.

### Architecture decisions

Document a decision when it changes a system boundary, dependency direction, public contract,
security model, persistence format, or major technology. Capture:

- context and forces
- chosen option
- rejected alternatives
- consequences and migration path
- verification method

Prefer additive evolution, compatibility adapters, optional fields, and small migrations over
big-bang rewrites.

## Domain-Driven Design

Apply DDD to express real domain knowledge, not as a naming ceremony.

### Strategic DDD

- Establish a ubiquitous language with the user and use it consistently in code and tests.
- Identify bounded contexts before sharing domain models across features.
- Give each bounded context ownership of its models and invariants.
- Integrate contexts through explicit contracts, events, or anti-corruption layers.
- Do not reuse one universal model merely because fields look similar.

### Tactical DDD

- Use an **Entity** when identity and lifecycle matter.
- Use an immutable **Value Object** when equality is defined by value.
- Use an **Aggregate** only when a consistency boundary must enforce invariants atomically.
- Keep invariants inside the aggregate or domain type that owns them.
- Use a **Domain Service** only for domain behavior that naturally belongs to no entity or value
  object.
- Define repository interfaces as domain/application ports; implement persistence outside the
  domain.
- Name domain events in past tense and publish them only after the corresponding state change is
  valid.

Avoid anemic models whose rules live entirely in controllers or service classes. Also avoid
forcing aggregates, repositories, or events onto CRUD-only teaching examples.

## SOLID

All generated, modified, reviewed, or refactored code must be checked against SOLID.

### Single Responsibility Principle

- Give each module, class, and function one clear reason to change.
- Separate orchestration, domain decisions, I/O, configuration, policy, persistence, and logging.
- Split god objects and vague helper modules along domain responsibilities.

### Open/Closed Principle

- Add strategies, policies, adapters, or implementations at genuine variation points.
- Avoid repeatedly expanding central conditional logic for every new tool or site.
- Do not create speculative extension frameworks without a second concrete use case.

### Liskov Substitution Principle

- Alternative implementations must preserve contracts, error semantics, and side-effect
  expectations.
- Do not strengthen preconditions or return weaker guarantees in a subtype or adapter.

### Interface Segregation Principle

- Keep ports small and consumer-focused.
- Do not force a read-only consumer to depend on mutation, persistence, or browser methods.

### Dependency Inversion Principle

- High-level policy must not depend directly on low-level framework or vendor details.
- Inject clocks, IDs, stores, external clients, and policy decisions when deterministic tests or
  substitution require it.
- Prefer composition over inheritance and explicit construction over hidden service location.

When a SOLID problem exists:

1. name the concrete problem
2. identify the affected principle
3. explain its cost in this use case
4. propose the smallest cleaner boundary
5. implement only within the authorized scope

## Test-Driven Development

Use Red-Green-Refactor for behavior changes.

### Red

- Express one observable behavior or invariant in a focused test.
- Run it and capture a meaningful failure whenever feasible.
- Ensure it fails for the intended reason, not because of broken setup.

### Green

- Implement the smallest production change that satisfies the behavior.
- Run the focused test and relevant regression tests.
- Do not mix opportunistic refactoring into this phase.

### Refactor

- Improve names, duplication, boundaries, and design only after green state.
- Keep behavior unchanged and rerun the tests after each meaningful refactor.

For legacy behavior, add a characterization test before changing it. If test-first is impractical
for documentation, generated configuration, an exploratory spike, or an emergency repair, state
the reason and add the closest useful automated verification.

### Test quality

- Test public behavior, domain invariants, contracts, and failure paths.
- Prefer deterministic unit tests for domain logic.
- Use fakes at owned ports and mocks only at narrow interaction boundaries.
- Do not mock the code under test or assert private implementation details.
- Add integration tests for adapters and contract tests for external boundaries.
- Keep browser and end-to-end tests few, isolated, and focused on critical paths.
- Never use arbitrary sleeps as the primary synchronization mechanism.
- A bug fix requires a regression test that fails before the fix when feasible.

## Security and operational quality

- Apply least privilege and explicit allowlists at external execution boundaries.
- Never hardcode or log credentials, cookies, tokens, private keys, or personal data.
- Normalize and validate captured or external data before reuse.
- Make state ownership, persistence, expiry, and cleanup explicit.
- Produce structured, safe diagnostics for policy decisions and failures.
- Separate retryable, validation, policy, dependency, and programming errors.
- Avoid uncontrolled replay, arbitrary code execution, and implicit network access.

## Teaching-project constraints

- The core teaching path must run locally without Docker.
- Core MVPs must not depend on external websites, paid APIs, or real credentials.
- Optional integrations must be clearly marked, isolated, and safe by default.
- Every introduced tool needs one small runnable MVP and a documented command.
- Every browser run needs an isolated context and deterministic cleanup.
- Configuration belongs in the local profile when it represents site-specific behavior.
- Discovery, normalization, policy, replay, and validation must remain explicit steps.
- Keep the examples small enough to explain in one lesson.

## Definition of Done

A change is done only when all applicable points are true:

- acceptance criteria are satisfied
- focused tests and relevant regression tests pass
- Red-Green-Refactor evidence exists or an exception is documented
- domain invariants and boundaries remain explicit
- SOLID review found no unaddressed material issue
- security and failure paths were considered
- documentation and runnable commands match the implementation
- relevant Todo state and summaries are accurate
- unrelated user changes remain untouched
- remaining risks, warnings, and baseline failures are reported clearly

The governing principle is:

**Understand the domain, protect the boundaries, prove behavior with tests, and deliver the
smallest maintainable slice.**
