<!-- Sync Impact Report
Version: 0.1.0 -> 1.0.0
Modifications:
- Initialized core principles for Next.js and Python stack
Updates:
- .specify/templates/plan-template.md: ✅ updated
-->
# Goblin Ledger Constitution

## Core Principles

### I. Type Safety & Validation
All frontend code must use TypeScript with strict mode enabled. All backend Python code must use explicit type hints and a validation library for API boundaries. No `any` types or implicit typing allowed.

### II. Clear Separation of Concerns
The frontend handles presentation, state management, and user interaction. The backend handles business rules, data persistence, and authorization. Domain logic must never leak into frontend components.

### III. Test-Driven / High Confidence
Critical paths, especially those dealing with ledgers or financial calculations, must have comprehensive automated tests. Backend services and complex frontend state must be independently testable. Tests are written before or alongside implementation.

### IV. Environment Consistency
Maintain explicit `.env` configurations. Use precise dependency management (`pnpm` or `npm` for frontend, `uv` or `.venv` for backend) to guarantee reproducible builds across all environments.

## Development Constraints

The primary technology stack is Next.js (App Router) with Tailwind CSS v4 on the frontend, and Python on the backend. No new primary languages or frameworks may be introduced without amending this constitution.

## Quality Gates & Workflow

Code must pass linters (`eslint`), type checkers, and automated tests before it can be merged. Every Pull Request must be reviewed against these Constitution principles.

## Governance

This Constitution supersedes all other practices. Any team member may propose amendments. Amendments require documentation, team approval, and a Version increment.

**Version**: 1.0.0 | **Ratified**: 2026-03-01 | **Last Amended**: 2026-03-01
