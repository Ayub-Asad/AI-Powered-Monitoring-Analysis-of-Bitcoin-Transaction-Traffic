# Project Instructions

This repository contains our Smart India Hackathon project:
Bitcoin Transaction Analysis.

Before making any changes:

1. Read PROJECT_CONTEXT.md.
2. Inspect the existing repository structure.
3. Do not redesign completed architecture without a clear reason.
4. Do not replace existing working code unnecessarily.
5. Preserve existing dataset schemas unless a change is explicitly justified.
6. Work incrementally.
7. Test changes before considering a task complete.
8. After completing a major task, update PROJECT_CONTEXT.md.

## Development Philosophy

Prefer:
- modular code
- simple implementations
- reproducible pipelines
- clear interfaces between modules
- explainable ML
- maintainable code

Avoid:
- unnecessary dependencies
- rewriting working components
- introducing architecture changes without discussion
- creating duplicate implementations

## Current Pipeline

Dataset
→ Ingestion
→ Feature Engineering
→ ML
→ Graph
→ API
→ Dashboard
→ Explainability
→ Polish

When assigned a task, focus only on the relevant stage unless another
stage must be changed for integration.