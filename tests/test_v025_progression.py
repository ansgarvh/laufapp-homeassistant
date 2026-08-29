from datetime import date, timedelta
from types import SimpleNamespace
import sqlite3

import performance_marks_v025 as perf
import training


def conn():
    c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE runs(id INTEGER PRIMARY KEY,started_at TEXT,distance_km REAL,duration_s REAL,source TEXT)')
    return c


def add_week(c, week_start, km, long_km):
    c.execute('INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)',
              ((week_start+timedelta(days=1)).isoformat()+'T08:00:00',long_km,long_km*330,'manual'))
    rest=max(0.0,km-long_km)
    if rest:
        c.execute('INSERT INTO runs(started_at,distance_km,duration_s,source) VALUES(?,?,?,?)',
                  ((week_start+timedelta(days=4)).isoformat()+'T18:00:00',rest,rest*340,'manual'))


def monday(d):return d-timedelta(days=d.weekday())


def test_sustained_training_after_pb_creates_bounded_progression_signal():
    c=conn();today=date.today();anchor=today-timedelta(days=126)
    pre_end=monday(anchor)
    for i in range(8):add_week(c,pre_end-timedelta(weeks=8-i),40,18)
    recent_end=monday(today)
    for i in range(8):add_week(c,recent_end-timedelta(weeks=8-i),55,26)
    signal=perf.progression_signal(c,{'date':anchor.isoformat()})
    assert signal['eligible'] is True
    assert 0 < signal['adjustment'] <= .025
    assert signal['current_weekly_km'] > signal['pre_pb_weekly_km']


def test_inconsistent_training_does_not_create_automatic_improvement():
    c=conn();today=date.today();anchor=today-timedelta(days=126);recent_end=monday(today)
    for i in (0,3,7):add_week(c,recent_end-timedelta(weeks=8-i),30,15)
    signal=perf.progression_signal(c,{'date':anchor.isoformat()})
    assert signal['eligible'] is False
    assert signal['adjustment']==0.0


def test_wrapper_can_move_pb_pinned_prediction_but_never_more_than_cap():
    c=conn();today=date.today();anchor=today-timedelta(days=126)
    pre_end=monday(anchor);recent_end=monday(today)
    for i in range(8):add_week(c,pre_end-timedelta(weeks=8-i),40,18)
    for i in range(8):add_week(c,recent_end-timedelta(weeks=8-i),60,28)
    pb=96*60+8
    fake=SimpleNamespace()
    fake.predict_distance=lambda _c,_t:{'distance_km':21.0975,'predicted_seconds':pb,'predicted_time':training.hms(pb),'confidence':.8,'range_text':'','performance_anchor':{'distance_km':21.0975,'duration_s':pb,'date':anchor.isoformat(),'source':'race','label':'HM'},'improvement_since_best_seconds':0,'notes':[]}
    fake.riegel=training.riegel;fake.hms=training.hms
    perf.install(fake,fake)
    out=fake.predict_distance(c,21.0975)
    assert out['predicted_seconds'] < pb
    assert out['predicted_seconds'] >= round(pb*.975)-1
    assert out['improvement_since_best_seconds'] > 0
