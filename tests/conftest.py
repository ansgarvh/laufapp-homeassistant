import os, sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

APP=Path(__file__).resolve().parents[1]/'laufapp'/'app'
sys.path.insert(0,str(APP))

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('LAUFAPP_DATA_DIR',str(tmp_path/'data'))
    monkeypatch.setenv('LAUFAPP_OPTIONS_FILE',str(tmp_path/'options.json'))
    monkeypatch.setenv('LAUFAPP_TRANSFER_DIR',str(tmp_path/'transfer'))
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    import main
    with TestClient(main.app) as c:
        yield c

@pytest.fixture
def setup_client(client):
    from datetime import date, timedelta
    race=(date.today()+timedelta(days=70)).isoformat()
    r=client.post('/api/setup',json={'race_name':'Test Marathon','distance_km':42.195,'race_date':race,'goal_seconds':3*3600+20*60,'training_days':[1,3,4,6]})
    assert r.status_code==200, r.text
    return client
