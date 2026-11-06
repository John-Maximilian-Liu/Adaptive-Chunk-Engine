# Contributing

1. Use feature branches `cursor/<name>-606a` (Cloud Agent convention) or team conventions.
2. Prefer vertical slices that remain runnable.
3. Keep canonical schemas provider-neutral.
4. Do not report external provider success without a real response.
5. Optional adapters must degrade with honest health reasons.
6. Run `pytest` and frontend tests before opening a PR.
7. Never commit secrets.
