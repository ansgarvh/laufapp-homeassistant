# Laufapp roadmap

Status labels are explicit: **implemented** means present in the repository; **planned** means not yet complete and must not be represented as available.

## DONE

- **Implemented (v0.1.3):** persistent schema-2 SQLite storage, additive legacy migration, pre-migration integrity-checked backup, rollback on migration failure, and downgrade rejection.
- **Implemented (v0.1.3):** persistent Apple Health background jobs with queryable progress, retry/restart recovery, transactional import, deduplication, and a 24-calendar-month filter.
- **Implemented (v0.1.3):** storage for detailed run samples, derived cadence, GPX routes, elevations, and derived ascent where input data permits.
- **Implemented:** mobile-first Heute/Woche/Fortschritt/Coach/Mehr shell; four configurable weekly running days; race targets; weekly plans/status/movement; shoes; marks and uncertainty-aware predictions.
- **Implemented:** server-side AI key/budget handling and explicit accept/reject gating for plan-change suggestions.
- **Implemented:** authenticated-Ingress header validation, direct remote-access blocking, localhost health checks, and a normally unpublished port 8099.
- **Implemented:** GitHub custom-repository layout and CI for compile, JavaScript syntax, pytest, and Docker build.

## NEXT

1. **Implemented in v0.1.4; production validation pending:** enable `ingress_stream: true` and protect it with a regression test to address large Health uploads stalling through Home Assistant Ingress.
2. **Planned:** validate a real, large native Apple Health export end-to-end through Home Assistant/Nabu Casa on the Beelink, including upload completion, resource use, database integrity, and deduplication.
3. **Planned:** verify background import phase/status polling, browser close/minimize behavior, retry, and restart recovery in the production Home Assistant UI.
4. **Planned:** design authenticated, idempotent Health Auto Export REST/JSON ingestion that retains detailed workout series and routes without creating thousands of Home Assistant entities.
5. **Planned:** add detailed run-analysis views for splits, pace, heart rate, power, cadence, running dynamics, elevation, and route.
6. **Planned:** improve and calibrate prediction quality only after sufficient imported personal history exists; continue showing uncertainty rather than false precision.
7. **Planned:** verify current official OpenAI API model identifiers, API design, and pricing, then configure the production AI Coach within the intended budget.
8. **Planned:** continue original mobile UI polish and real-device regression checks at approximately 390 px and 320 px without horizontal overflow.

## LATER

- **Planned:** safe continuous Apple Health synchronization following the REST ingestion design.
- **Planned:** runner-specific learning for mileage tolerance, quality-session response, long-run recovery, pace/heart-rate relationships, race transfer, and taper response, based only on accumulated local evidence.
- **Planned:** richer weekly editing and neighboring-week scheduling while preserving completed, skipped, and deliberately moved sessions.
- **Planned:** conservative adaptive planning using recovery and prior response, with explicit user control and deload/taper safeguards.
- **Planned:** stronger multi-signal critical-speed/endurance prediction models and confidence calibration.
- **Planned:** evidence-search improvements prioritizing peer-reviewed research and reputable consensus bodies, with uncertainty clearly communicated.
- **Planned:** optional shoe-response analysis only when enough data supports defensible conclusions.
