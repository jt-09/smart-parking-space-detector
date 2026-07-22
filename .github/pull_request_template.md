## Summary

<!-- What does this PR change and why? -->

## Linked issue

Closes #

## Key changes

-

## Test plan

```bash
uv sync --locked --all-groups
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest --cov=smart_parking --cov-fail-under=85
```

Results:

-

## Development timeline

Owner window: 2026-07-22 through 2026-07-28 (+10:00).

<!-- List planned/executed developmental commits with timestamps. -->

-

## Privacy / licensing

- [ ] No secrets, footage, model weights, databases, or generated media committed
- [ ] License and attribution notes updated if needed

## Checklist

- [ ] Acceptance criteria for the linked issue are met
- [ ] Docs / changelog updated when applicable
- [ ] Separate review pass completed (not claimed as independent human approval)
