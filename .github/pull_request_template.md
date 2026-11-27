## What and why

<!-- One concern per PR. Link the milestone or issue. -->

## Checks

- [ ] `uv run pytest` and `uv run mypy` pass
- [ ] If templates or CSS changed: golden snapshot updated on purpose (`UPDATE_GOLDEN=1 uv run pytest`)
- [ ] If a model changed: ran `uv run timeleaf schema` and committed `docs/schemas/`
- [ ] If a decision in docs/PLAN.md §2.2 changed: new ADR in `docs/adr/`
