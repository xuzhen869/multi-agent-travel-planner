"""认证流程 API 测试：注册 / 登录 / 刷新 / 登出 / 获取用户"""


def _register(client, email="user@example.com", password="password123", name="测试用户"):
    return client.post("/api/auth/register", json={
        "email": email,
        "password": password,
        "display_name": name,
    })


def _login(client, email, password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _auth_header(client, email):
    _register(client, email=email)
    token = _login(client, email).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ——— 注册 ———


def test_register_success(client):
    r = _register(client, email="ok@example.com")
    assert r.status_code == 201
    data = r.json()
    assert data["access_token"]
    assert data["refresh_token"]
    assert data["token_type"] == "bearer"


def test_register_duplicate_email_conflict(client):
    _register(client, email="dup@example.com")
    r = _register(client, email="dup@example.com")
    assert r.status_code == 409


def test_register_invalid_email_rejected(client):
    r = _register(client, email="not-an-email")
    assert r.status_code == 422


def test_register_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "pw@example.com", "password": "123"})
    assert r.status_code == 422


# ——— 登录 ———


def test_login_success(client):
    _register(client, email="login@example.com")
    r = _login(client, "login@example.com")
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    _register(client, email="wrong@example.com")
    r = client.post("/api/auth/login", json={"email": "wrong@example.com", "password": "bad-pass"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = _login(client, "nobody@example.com")
    assert r.status_code == 401


# ——— 获取当前用户 ———


def test_get_me(client):
    headers = _auth_header(client, "me@example.com")
    r = client.get("/api/users/me", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "me@example.com"
    assert data["display_name"] == "测试用户"
    assert data["is_first_time"] is True


def test_get_me_missing_header_rejected(client):
    """缺失 Authorization header → 422（Header(...) 必填校验，后端既有设计）"""
    r = client.get("/api/users/me")
    assert r.status_code == 422


def test_get_me_invalid_token_rejected(client):
    """携带无效令牌 → 401"""
    r = client.get("/api/users/me", headers={"Authorization": "Bearer invalid-token"})
    assert r.status_code == 401


def test_get_me_wrong_auth_scheme(client):
    """非 Bearer 认证格式 → 401"""
    r = client.get("/api/users/me", headers={"Authorization": "Token abc"})
    assert r.status_code == 401


# ——— 偏好 ———


def test_get_preferences_defaults(client):
    headers = _auth_header(client, "pref@example.com")
    r = client.get("/api/users/me/preferences", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["preferred_hotel_star"] == 4
    assert data["budget_default_currency"] == "CNY"


def test_update_preferences_turns_off_first_time(client):
    headers = _auth_header(client, "pref2@example.com")
    r = client.put("/api/users/me/preferences", headers=headers, json={
        "preferred_hotel_star": 5,
        "preferred_flight_class": "business",
        "pace": "fast",
        "interests": ["美食"],
        "dietary": [],
        "budget_default_currency": "CNY",
        "default_travelers": [{"age": 30, "type": "adult"}],
    })
    assert r.status_code == 200
    assert r.json()["preferred_hotel_star"] == 5
    assert r.json()["is_first_time"] is False

    # is_first_time 已置为 False
    r = client.get("/api/users/me", headers=headers)
    assert r.json()["is_first_time"] is False


# ——— 刷新 & 登出 ———


def test_refresh_token(client):
    _register(client, email="refresh@example.com")
    refresh = _login(client, "refresh@example.com").json()["refresh_token"]
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_refresh_invalid_token(client):
    r = client.post("/api/auth/refresh", json={"refresh_token": "garbage-token"})
    assert r.status_code == 401


def test_logout_revokes_refresh(client):
    _register(client, email="logout@example.com")
    refresh = _login(client, "logout@example.com").json()["refresh_token"]
    r = client.post("/api/auth/logout", json={"refresh_token": refresh})
    assert r.status_code == 204
    # 登出后刷新令牌已被撤销
    r = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401
