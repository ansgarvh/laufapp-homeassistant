def test_mark_completed_persists_and_is_returned_by_week_api(setup_client):
    client = setup_client
    week = client.get('/api/week').json()
    workout = week['workouts'][0]

    response = client.post(f"/api/workouts/{workout['id']}/status", json={'status': 'completed'})
    assert response.status_code == 200, response.text
    assert response.json() == {'ok': True}

    refreshed = client.get(f"/api/week?start={week['week_start']}").json()
    stored = next(item for item in refreshed['workouts'] if item['id'] == workout['id'])
    assert stored['status'] == 'completed'


def test_completed_workout_can_be_changed_to_skipped_and_back(setup_client):
    client = setup_client
    week = client.get('/api/week').json()
    workout = week['workouts'][0]

    for status in ('completed', 'skipped', 'completed'):
        response = client.post(f"/api/workouts/{workout['id']}/status", json={'status': status})
        assert response.status_code == 200, response.text
        refreshed = client.get(f"/api/week?start={week['week_start']}").json()
        stored = next(item for item in refreshed['workouts'] if item['id'] == workout['id'])
        assert stored['status'] == status
