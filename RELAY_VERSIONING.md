# HAE relay versioning

The Home Assistant custom integration in `custom_components/laufapp_hae_relay` has an independent release lifecycle from the Laufapp application.

## Core rule

A normal Laufapp release must **not** change `custom_components/laufapp_hae_relay/manifest.json` just to match the Laufapp application version.

The relay is deliberately small and transport-only. It receives the Home Assistant webhook request, applies transport/security limits, forwards the raw JSON body to the fixed internal Laufapp gateway and returns the upstream response. It does not parse workout names, Health Auto Export schemas, running metrics, predictions or training data.

Therefore changes to any of the following normally require only a Laufapp application/gateway update and **no Home Assistant relay update**:

- Health Auto Export workout or metric parsing
- German/English workout-name compatibility
- new detailed running metrics or GPS handling
- database/deduplication behavior
- prediction or training-plan logic
- UI changes
- normal Laufapp application version bumps

## When the relay version must change

Increase the relay version only when the relay implementation itself changes, for example:

- public webhook handling
- authentication/header transport
- internal relay endpoint or transport contract
- body-size, timeout, rate or concurrency limits
- Home Assistant webhook/client API compatibility
- security fixes in the relay

Any change to `custom_components/laufapp_hae_relay/__init__.py` must be accompanied by an explicit higher numeric SemVer version in `manifest.json`.

Conversely, changing only the relay manifest version without changing the relay implementation is prohibited. `.github/workflows/relay-versioning.yml` enforces both directions.

## Historical note

The functional relay code was last changed as part of Laufapp v0.2.13. Later Laufapp releases changed the relay manifest version together with the application version even though `__init__.py` did not change. The current repository keeps its existing manifest value rather than introducing a metadata downgrade, but from this policy onward the version is frozen until the relay implementation really changes.

This means an installed relay whose `__init__.py` is identical to the current repository does not need to be replaced solely because its historical manifest version differs from the Laufapp application version.

## Release checklist

For every Laufapp release:

1. Leave the relay source and relay manifest untouched unless the transport component itself needs a change.
2. If relay code changes, review the public webhook/security boundary separately and increase the relay SemVer.
3. Run the full relay regression tests, including large raw-body forwarding, limits, duplicate-webhook handling and internal gateway E2E.
4. State explicitly whether a Home Assistant Core restart is required. Normal Laufapp-only releases must not require one for the relay.
5. Real Home Assistant OS, Nabu Casa and iPhone/Health Auto Export integration remains a target-system verification boundary.
