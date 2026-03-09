## What does this PR do?

<!-- Brief description of the change -->

## Related issue

Closes #<!-- issue number -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Security fix
- [ ] Performance improvement
- [ ] Documentation
- [ ] Refactor

## Checklist

- [ ] Tests added or updated (`python -m pytest tests/ -v` passes)
- [ ] Type hints on all new functions
- [ ] No API keys or secrets in code or tests
- [ ] `black .` and `isort .` applied
- [ ] `CONTRIBUTING.md` steps followed

## For new interceptors

- [ ] Follows `openai_patch.py` pattern
- [ ] Uses `threading.Lock` for `_patch_state`
- [ ] Lazy-imports SDK with helpful error message
- [ ] Tests mock the SDK (no real API calls)
