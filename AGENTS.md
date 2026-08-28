# Conservative development rules

- Inspect the existing implementation and all affected callers before modifying code.
- Make only the minimal changes necessary for the requested behavior.
- Preserve backwards compatibility and persistent user data.
- Never make a destructive database migration without an explicit migration and backup path.
- Run compile, regression, integration, and synthetic end-to-end tests before every release.
- Do not release when any test fails.
- Preserve Home Assistant Ingress security; never expose the app by weakening its Ingress-only access protection.
- Preserve Apple Health background jobs, detailed running metrics, GPS data, deduplication, and persistent SQLite data across updates.
- Update the application version, changelog, and documentation consistently.
- Explicitly distinguish isolated/static tests from tests performed against a real Home Assistant installation.
