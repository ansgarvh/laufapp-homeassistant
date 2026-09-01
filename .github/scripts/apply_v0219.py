from pathlib import Path


def replace_exact(path, old, new, count=1):
    p = Path(path)
    text = p.read_text()
    actual = text.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} occurrence(s), found {actual}: {old[:80]!r}")
    p.write_text(text.replace(old, new, count))


replace_exact(
    "laufapp/app/main.py",
    """@app.post('/api/workouts/{wid}/status')
def api_status(wid:int,p:StatusPayload):
    with db_conn() as c:
        if not c.execute(\"SELECT id FROM workouts WHERE id=?\",(wid,)).fetchone():raise HTTPException(404,'Training nicht gefunden.')
        c.execute(\"UPDATE workouts SET status=?,manual_override=1,modified_by='user' WHERE id=?\",(p.status,wid));return {'ok':True}
""",
    """@app.post('/api/workouts/{wid}/status')
def api_status(wid:int,p:StatusPayload):
    with db_conn() as c:
        workout=c.execute(\"SELECT id,status,linked_run_id FROM workouts WHERE id=?\",(wid,)).fetchone()
        if not workout:raise HTTPException(404,'Training nicht gefunden.')
        if workout['linked_run_id'] is not None:
            if p.status!='completed':raise HTTPException(409,'Diese Einheit ist mit einem Lauf verknüpft. Löse zuerst die Aktivitätsverknüpfung, bevor der Abschlussstatus geändert wird.')
            return {'ok':True,'status':'completed','linked_run_id':int(workout['linked_run_id'])}
        c.execute(\"UPDATE workouts SET status=?,manual_override=1,modified_by='user' WHERE id=?\",(p.status,wid))
        return {'ok':True,'status':p.status,'linked_run_id':None}
""",
)

p = Path("laufapp/app/static/app.js")
text = p.read_text()
start = text.index("  function openWorkoutMenu(id){")
end = text.index("  function openMoveModal", start)
replacement = '''  function openWorkoutMenu(id){
    const w=state.week?.workouts.find(x=>x.id===id);if(!w)return;const d=w.details||{},linked=w.linked_run_id!==null&&w.linked_run_id!==undefined;
    const actions=w.status==='completed'
      ? linked
        ? `<div class="quality-ok"><b>✓</b><span>Diese Absolvierung stammt aus einem verknüpften Lauf. Sie kann hier nicht manuell zurückgenommen werden.</span></div>`
        : `<div class="button-row"><button class="button" data-a="undo-done">Absolvierung zurücknehmen</button></div>`
      : `<div class="button-row"><button class="button primary" data-a="done">Als absolviert markieren</button><button class="button" data-a="move">Verschieben</button><button class="button danger" data-a="skip">Ausgefallen</button></div>`;
    modal(w.title,`<div class="workout-kicker"><span class="pill ${esc(w.workout_type)}">${esc(TYPE[w.workout_type]||w.workout_type)}</span><span class="small muted">${niceDate(w.scheduled_date)}</span></div><div class="workout-stats"><span><b>${fmt1(w.distance_km)} km</b>Distanz</span><span><b>${esc(w.pace_text||'nach RPE')}</b>Pace</span><span><b>${esc(d.rpe_target||'–')}</b>RPE</span></div><div class="workout-purpose">${esc(d.instructions||'')}</div>${actions}`,m=>{
      m.querySelector('[data-a="done"]')?.addEventListener('click',()=>{closeModal();setWorkoutStatus(id,'completed')});
      m.querySelector('[data-a="undo-done"]')?.addEventListener('click',()=>{closeModal();setWorkoutStatus(id,'planned')});
      m.querySelector('[data-a="move"]')?.addEventListener('click',()=>{closeModal();openMoveModal(id,w.scheduled_date)});
      m.querySelector('[data-a="skip"]')?.addEventListener('click',()=>{closeModal();setWorkoutStatus(id,'skipped')});
    })
  }
'''
p.write_text(text[:start] + replacement + text[end:])
replace_exact(
    "laufapp/app/static/app.js",
    "  async function setWorkoutStatus(id,status){try{await api(`api/workouts/${id}/status`,{method:'POST',body:{status}});toast(status==='completed'?'Einheit als absolviert markiert.':status==='skipped'?'Einheit als ausgefallen markiert.':'Status aktualisiert.');render()}catch(e){toast(e.message,true)}}",
    "  async function setWorkoutStatus(id,status){try{await api(`api/workouts/${id}/status`,{method:'POST',body:{status}});toast(status==='completed'?'Einheit als absolviert markiert.':status==='skipped'?'Einheit als ausgefallen markiert.':status==='planned'?'Absolvierung zurückgenommen.':'Status aktualisiert.');render()}catch(e){toast(e.message,true)}}",
)

Path("laufapp/app/main_v0219.py").write_text('''"""Laufapp v0.2.19 manual-completion undo release.\n\nAdds a safe reversible manual workout-completion state while preserving linked\nrun authority and the complete v0.2.18 multi-race/security/HAE stack.\n"""\nfrom __future__ import annotations\n\nimport main_v0218 as previous\n\nAPP_VERSION = "0.2.19"\n\n_module = previous\nfor _ in range(30):\n    if _module is None:\n        break\n    if hasattr(_module, "APP_VERSION"):\n        _module.APP_VERSION = APP_VERSION\n    _module = getattr(_module, "previous", None)\n\ncore = previous.core\ncore.db_module.APP_VERSION = APP_VERSION\ncore.legacy.APP_VERSION = APP_VERSION\ncore.legacy.app.version = APP_VERSION\ncore.training.VERSION = APP_VERSION\n\nprocess_health_auto_export_request = previous.process_health_auto_export_request\napp = previous.app\n''')

replace_exact("laufapp/config.yaml", 'version: "0.2.18"', 'version: "0.2.19"')
replace_exact("laufapp/Dockerfile", "ARG BUILD_VERSION=0.2.18", "ARG BUILD_VERSION=0.2.19")
replace_exact("laufapp/run.sh", "uvicorn main_v0218:app", "uvicorn main_v0219:app")
replace_exact("laufapp/run.sh", "port=8099 version=0.2.18", "port=8099 version=0.2.19")
replace_exact("laufapp/run.sh", "port=8100 version=0.2.18", "port=8100 version=0.2.19")
replace_exact("laufapp/app/health_auto_export_gateway.py", "from main_v0218 import APP_VERSION, process_health_auto_export_request", "from main_v0219 import APP_VERSION, process_health_auto_export_request")
replace_exact("laufapp/app/static/index.html", "app.js?v=0.2.18", "app.js?v=0.2.19")
replace_exact("laufapp/app/static/sw.js", "const CACHE='laufapp-v0.2.18'", "const CACHE='laufapp-v0.2.19'")
replace_exact("laufapp/app/static/sw.js", "app.js?v=0.2.18", "app.js?v=0.2.19")
replace_exact("custom_components/laufapp_hae_relay/manifest.json", '"version": "0.2.18"', '"version": "0.2.19"')
replace_exact("tests/conftest.py", "import main_v0218\n    with TestClient(main_v0218.app)", "import main_v0219\n    with TestClient(main_v0219.app)")

path = Path("tests/test_release_static.py")
t = path.read_text()
replacements = {
    "assert cfg['version']=='0.2.18'": "assert cfg['version']=='0.2.19'",
    "assert 'APP_VERSION = \"0.2.18\"' in (ROOT/'laufapp/app/main_v0218.py').read_text()": "assert 'APP_VERSION = \"0.2.19\"' in (ROOT/'laufapp/app/main_v0219.py').read_text()",
    "assert 'ARG BUILD_VERSION=0.2.18'": "assert 'ARG BUILD_VERSION=0.2.19'",
    "assert 'main_v0218:app'": "assert 'main_v0219:app'",
    "assert '# Laufapp v0.2.18'": "assert '# Laufapp v0.2.19'",
    "assert '## v0.2.18 – 2026-08-31'": "assert '## v0.2.19 – 2026-09-01'",
    "assert (ROOT/'RELEASE_NOTES_v0.2.18.md').exists()": "assert (ROOT/'RELEASE_NOTES_v0.2.19.md').exists()",
    "assert 'Laufapp v0.2.18' in (ROOT/'RELEASE_NOTES_v0.2.18.md').read_text()": "assert 'Laufapp v0.2.19' in (ROOT/'RELEASE_NOTES_v0.2.19.md').read_text()",
    "assert \"const CACHE='laufapp-v0.2.18'\" in sw": "assert \"const CACHE='laufapp-v0.2.19'\" in sw",
    "for asset in ['app.js?v=0.2.18'": "for asset in ['app.js?v=0.2.19'",
    "assert 'from main_v0218 import APP_VERSION' in gateway": "assert 'from main_v0219 import APP_VERSION' in gateway",
    "assert manifest['version']=='0.2.18'": "assert manifest['version']=='0.2.19'",
}
for old, new in replacements.items():
    if t.count(old) != 1:
        raise SystemExit(f"test_release_static.py marker mismatch: {old}")
    t = t.replace(old, new, 1)
path.write_text(t)

Path("tests/test_v0219_manual_completion_undo.py").write_text('''from pathlib import Path\n\n\ndef _first_workout(client):\n    week=client.get('/api/week').json()\n    assert week['workouts']\n    return week['workouts'][0]\n\n\ndef test_manual_completion_can_be_reverted_to_planned(setup_client):\n    client=setup_client\n    w=_first_workout(client)\n    r=client.post(f"/api/workouts/{w['id']}/status",json={'status':'completed'})\n    assert r.status_code==200, r.text\n    row=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])\n    assert row['status']=='completed' and row['linked_run_id'] is None\n    r=client.post(f"/api/workouts/{w['id']}/status",json={'status':'planned'})\n    assert r.status_code==200, r.text\n    row=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])\n    assert row['status']=='planned' and row['linked_run_id'] is None\n    assert row['manual_override']==1 and row['modified_by']=='user'\n\n\ndef test_linked_completion_cannot_be_reverted_or_skipped(setup_client):\n    client=setup_client\n    w=_first_workout(client)\n    r=client.post('/api/runs',json={'started_at':f"{w['scheduled_date']}T08:00:00+00:00",'distance_km':w['distance_km'],'duration_s':max(1800,w['distance_km']*330),'source':'manual'})\n    assert r.status_code==200, r.text\n    linked=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])\n    assert linked['status']=='completed' and linked['linked_run_id'] is not None\n    for status in ('planned','skipped'):\n        r=client.post(f"/api/workouts/{w['id']}/status",json={'status':status})\n        assert r.status_code==409, r.text\n    linked=next(x for x in client.get('/api/week').json()['workouts'] if x['id']==w['id'])\n    assert linked['status']=='completed' and linked['linked_run_id'] is not None\n\n\ndef test_ui_offers_undo_only_for_manual_unlinked_completion():\n    js=(Path(__file__).resolve().parents[1]/'laufapp/app/static/app.js').read_text()\n    assert 'Absolvierung zurücknehmen' in js\n    assert "setWorkoutStatus(id,'planned')" in js\n    assert 'Diese Absolvierung stammt aus einem verknüpften Lauf' in js\n    assert "w.linked_run_id!==null&&w.linked_run_id!==undefined" in js\n''')

readme = Path("README.md").read_text()
readme = readme.replace("# Laufapp v0.2.18", "# Laufapp v0.2.19", 1)
marker = "## Neu in v0.2.18 – mehrere Wettkampfziele und bessere Rennanlage\n"
section = '''## Neu in v0.2.19 – manuelle Absolvierung zurücknehmen\n\n- Eine ohne verknüpften Lauf manuell als **absolviert** markierte Einheit kann im Einheiten-Menü über **„Absolvierung zurücknehmen“** wieder auf `geplant` gesetzt werden.\n- Ein tatsächlich verknüpfter Lauf bleibt autoritativ: Solange `linked_run_id` gesetzt ist, verhindert das Backend das Zurücksetzen auf `geplant` oder `ausgefallen`, damit Planstatus und Laufdaten nicht widersprüchlich werden.\n- Die Rücknahme löscht keine Einheit und keine Laufdaten. Die Einheit bleibt als manuell berührt geschützt (`manual_override=1`).\n- Keine Datenbankschemamigration; Trainingsengine, Mehrfachrennen, HAE/Nabu/Ingress und Security bleiben unverändert.\n\n\n'''
if marker not in readme:
    raise SystemExit("README insertion marker missing")
readme = readme.replace(marker, section + marker, 1)
readme = readme.replace("v0.2.18 benötigt **keine Datenbankschemamigration**.", "v0.2.19 benötigt **keine Datenbankschemamigration**.", 1)
readme = readme.replace("v0.2.18-Entry-Point", "v0.2.19-Entry-Point", 1)
readme = readme.replace("uvicorn main_v0218:app", "uvicorn main_v0219:app", 1)
readme = readme.replace("`RELEASE_NOTES_v0.2.18.md`, `TRAINING_ENGINE.md`", "`RELEASE_NOTES_v0.2.19.md`, `TRAINING_ENGINE.md`", 1)
Path("README.md").write_text(readme)

changelog = Path("CHANGELOG.md").read_text()
header = "# Laufapp Changelog\n\n"
entry = '''## v0.2.19 – 2026-09-01\n\n- Manuell ohne verknüpften Lauf als `completed` markierte Planaktivitäten können über **„Absolvierung zurücknehmen“** wieder auf `planned` gesetzt werden.\n- Verknüpfte Läufe bleiben autoritativ: Das Backend blockiert `planned`/`skipped` für Workouts mit `linked_run_id`, statt widersprüchliche Statusdaten zu erzeugen.\n- Die Rücknahme behält `manual_override=1` und `modified_by=user`, damit eine bewusst angefasste Einheit bei späterer Plangenerierung geschützt bleibt.\n- UI unterscheidet jetzt zwischen manuellem Abschluss und Abschluss durch verknüpften Lauf; bei verknüpften Läufen wird keine irreführende Undo-Aktion angeboten.\n- Neue Regressionen prüfen manuellen Completed→Planned-Roundtrip, verknüpfte Statussperre und UI-Hooks. Keine Datenbankschemamigration.\n\n'''
if not changelog.startswith(header):
    raise SystemExit("CHANGELOG header mismatch")
Path("CHANGELOG.md").write_text(header + entry + changelog[len(header):])

Path("RELEASE_NOTES_v0.2.19.md").write_text('''# Laufapp v0.2.19\n\n## Manuelle Absolvierung sicher zurücknehmen\n\nEine Planaktivität, die ohne verknüpften Lauf manuell als absolviert markiert wurde, kann im Einheiten-Menü wieder auf **geplant** gesetzt werden. Die Rücknahme löscht weder die Planaktivität noch Laufdaten.\n\nWorkouts mit einem echten `linked_run_id` werden bewusst anders behandelt: Der verknüpfte Lauf ist autoritativ. Das Backend lehnt ein Zurücksetzen auf `planned` oder `skipped` mit HTTP 409 ab, bis die Aktivitätsverknüpfung separat gelöst wurde. So können Status und vorhandener Lauf nicht widersprüchlich werden.\n\nKeine Datenbankschemamigration. Die v0.2.18-Mehrfachrennenlogik, Leistungsprofil-, Apple-Health-/HAE-, Nabu-Casa-/Ingress- und Security-Schichten bleiben erhalten.\n\nStatisch/isoliert und in Linux/Docker zu testen; die reale Home-Assistant-OS-/Ingress-Darstellung muss lokal verifiziert werden.\n''')
