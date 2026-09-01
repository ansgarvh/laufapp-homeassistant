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
- Treat `custom_components/laufapp_hae_relay` as an independently versioned transport component. Never bump its manifest version merely to match a Laufapp application release. Change the relay version only when the relay implementation itself changes, and then increase its numeric SemVer deliberately and run the dedicated relay/security regressions. See `RELAY_VERSIONING.md`.
- Explicitly distinguish isolated/static tests from tests performed against a real Home Assistant installation.
