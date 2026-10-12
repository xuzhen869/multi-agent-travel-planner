"""行程 CRUD API 测试 — mock Celery，避免依赖真实 worker 与外部 Agent 服务"""

import pytest


def _register(client, email, password="password123"):
    return client.post("/api/auth/register", json={
        "email": email, "password": password,
    })


class _NoopRunner:
    """无操作假 Runner：提供 delay 方法但不做任何事（替代 Celery 调用）"""

    @staticmethod
    def delay(*args, **kwargs):
        pass


def _auth_header(client, email):
    _register(client, email)
    token = client.post("/api/auth/login", json={
        "email": email, "password": "password123",
    }).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_trip(client, headers, **overrides):
    payload = {
        "destination": "东京",
        "departure_city": "上海",
        "start_date": "2026-10-01",
        "end_date": "2026-10-05",
        "travelers": [{"age": 30, "type": "adult"}],
        "budget": {"total": 20000, "currency": "CNY"},
        "mode": "recommend",
    }
    payload.update(overrides)
    return client.post("/api/trips", headers=headers, json=payload)


# ——— 创建 ———


def test_create_trip_triggers_planner(client, monkeypatch):
    """创建行程应返回 recommending 状态，并触发 Celery 规划任务"""
    called = {}

    class _FakeRunner:
        @staticmethod
        def delay(*args, **kwargs):
            called["args"] = args

    monkeypatch.setattr("app.services.planner_service.run_planner", _FakeRunner)

    headers = _auth_header(client, "trip@example.com")
    r = _create_trip(client, headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "recommending"
    assert data["events_url"].startswith("/api/trips/")
    assert called["args"], "Celery 规划任务未被触发"


def test_create_trip_missing_header_rejected(client):
    """缺失 Authorization header → 422（Header(...) 必填校验）"""
    r = _create_trip(client, {})
    assert r.status_code == 422


def test_create_trip_invalid_token_rejected(client):
    """携带无效令牌 → 401"""
    r = _create_trip(client, {"Authorization": "Bearer invalid-token"})
    assert r.status_code == 401


def test_create_trip_direct_mode(client, monkeypatch):
    """direct 模式创建后状态为 planning"""
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "direct@example.com")
    r = _create_trip(client, headers, mode="direct")
    assert r.status_code == 201
    assert r.json()["status"] == "planning"


# ——— 列表 ———


def test_list_trips(client, monkeypatch):
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "list@example.com")
    _create_trip(client, headers)
    r = client.get("/api/trips", headers=headers)
    assert r.status_code == 200
    trips = r.json()
    assert len(trips) == 1
    assert trips[0]["destination"] == "东京"
    assert trips[0]["status"] == "recommending"


def test_list_trips_isolated_between_users(client, monkeypatch):
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    h1 = _auth_header(client, "list-a@example.com")
    h2 = _auth_header(client, "list-b@example.com")
    _create_trip(client, h1)
    assert len(client.get("/api/trips", headers=h2).json()) == 0
    assert len(client.get("/api/trips", headers=h1).json()) == 1


# ——— 详情 ———


def test_get_trip_detail(client, monkeypatch):
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "detail@example.com")
    trip_id = _create_trip(client, headers).json()["trip_id"]
    r = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["request_params"]["destination"] == "东京"
    assert data["mode"] == "recommend"


def test_get_other_users_trip_forbidden(client, monkeypatch):
    """行程属于 A 用户，B 用户访问应 404"""
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    ha = _auth_header(client, "own@example.com")
    hb = _auth_header(client, "other@example.com")
    trip_id = _create_trip(client, ha).json()["trip_id"]
    r = client.get(f"/api/trips/{trip_id}", headers=hb)
    assert r.status_code == 404


def test_get_trip_not_found(client):
    headers = _auth_header(client, "nf@example.com")
    r = client.get("/api/trips/00000000-0000-0000-0000-000000000000", headers=headers)
    assert r.status_code == 404


# ——— 删除 ———


def test_delete_trip(client, monkeypatch):
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "del@example.com")
    trip_id = _create_trip(client, headers).json()["trip_id"]
    r = client.delete(f"/api/trips/{trip_id}", headers=headers)
    assert r.status_code == 204
    assert client.get(f"/api/trips/{trip_id}", headers=headers).status_code == 404


# ——— 方案选择边界 ———


def test_select_plan_recommend_no_plans(client, monkeypatch):
    """推荐模式但尚无任何方案（Celery 未执行完成）→ 400"""
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "sel@example.com")
    trip_id = _create_trip(client, headers).json()["trip_id"]
    r = client.post(f"/api/trips/{trip_id}/select/plan_1", headers=headers)
    assert r.status_code == 400


def test_select_plan_direct_no_selection(client, monkeypatch):
    """direct 模式方案未自动选定前选择 → 400（已由系统自动选定）"""
    monkeypatch.setattr("app.services.planner_service.run_planner", _NoopRunner)
    headers = _auth_header(client, "dsel@example.com")
    trip_id = _create_trip(client, headers, mode="direct").json()["trip_id"]
    r = client.post(f"/api/trips/{trip_id}/select/plan_direct", headers=headers)
    assert r.status_code == 400


# ——— 重新规划 ———


def test_regenerate_resets_and_retriggers(client, monkeypatch):
    calls = []

    class _FakeRunner:
        @staticmethod
        def delay(trip_id, mode):
            calls.append((trip_id, mode))

    monkeypatch.setattr("app.services.planner_service.run_planner", _FakeRunner)
    monkeypatch.setattr("app.tasks.planner_task.run_planner", _FakeRunner)

    headers = _auth_header(client, "regen@example.com")
    trip_id = _create_trip(client, headers).json()["trip_id"]

    r = client.post(f"/api/trips/{trip_id}/regenerate", headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "recommending"
    assert len(calls) == 2  # 创建 + 重新规划各触发一次


def test_trip_events_requires_auth(client):
    r = client.get("/api/trips/00000000-0000-0000-0000-000000000000/events")
    assert r.status_code == 401
