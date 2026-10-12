const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let accessToken: string | null = null;
let refreshToken: string | null = null;

export function setTokens(access: string, refresh: string) {
  accessToken = access;
  refreshToken = refresh;
  if (typeof window !== 'undefined') {
    localStorage.setItem('access_token', access);
    localStorage.setItem('refresh_token', refresh);
  }
}

export function loadTokens() {
  if (typeof window !== 'undefined') {
    accessToken = localStorage.getItem('access_token');
    refreshToken = localStorage.getItem('refresh_token');
  }
}

export function clearTokens() {
  accessToken = null;
  refreshToken = null;
  if (typeof window !== 'undefined') {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function isAuthenticated(): boolean {
  return !!accessToken;
}

async function refreshAccessToken(): Promise<boolean> {
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    return false;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  loadTokens();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };
  if (accessToken) {
    headers['Authorization'] = `Bearer ${accessToken}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && retry) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return request<T>(path, options, false);
    clearTokens();
    if (typeof window !== 'undefined') window.location.href = '/login';
    throw new Error('未登录');
  }

  if (res.status === 204) return undefined as T;

  if (!res.ok) {
    const error = await res.json().catch(() => ({ message: '请求失败' }));
    throw new Error(error.message || error.detail || '请求失败');
  }

  return res.json();
}

// ====== API 方法 ======

export const api = {
  // Auth
  register: (email: string, password: string, display_name?: string) =>
    request<import('@/types').TokenResponse>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name }),
    }),

  login: (email: string, password: string) =>
    request<import('@/types').TokenResponse>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),

  logout: () =>
    request<void>('/api/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  // User
  getMe: () => request<import('@/types').User>('/api/users/me'),

  updateMe: (data: { display_name?: string }) =>
    request<import('@/types').User>('/api/users/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getPreferences: () =>
    request<import('@/types').Preference>('/api/users/me/preferences'),

  updatePreferences: (data: Record<string, unknown>) =>
    request<import('@/types').Preference>('/api/users/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  getProfile: () =>
    request<import('@/types').UserProfile>('/api/users/me/profile'),

  refreshProfile: () =>
    request<import('@/types').UserProfile>('/api/users/me/profile/refresh', {
      method: 'POST',
    }),

  // Trips
  createTrip: (data: import('@/types').TripCreateRequest) =>
    request<import('@/types').PlanCreatedResponse>('/api/trips', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  listTrips: (offset = 0, limit = 20) =>
    request<import('@/types').TripListItem[]>(`/api/trips?offset=${offset}&limit=${limit}`),

  getTrip: (id: string) =>
    request<import('@/types').TripDetail>(`/api/trips/${id}`),

  selectPlan: (tripId: string, planId: string) =>
    request<import('@/types').TripDetail>(`/api/trips/${tripId}/select/${planId}`, {
      method: 'POST',
    }),

  deleteTrip: (id: string) =>
    request<void>(`/api/trips/${id}`, { method: 'DELETE' }),

  regenerateTrip: (id: string) =>
    request<import('@/types').PlanCreatedResponse>(`/api/trips/${id}/regenerate`, {
      method: 'POST',
    }),

  // OAuth
  getGoogleAuthUrl: () =>
    request<import('@/types').OAuthUrlResult>('/api/auth/oauth/google/url'),

  getGithubAuthUrl: () =>
    request<import('@/types').OAuthUrlResult>('/api/auth/oauth/github/url'),

  // Lookup — 城市搜索 / IATA / 汇率 / 地理编码 / 路线规划
  searchCities: (q: string) =>
    request<{ cities: import('@/types').CityOption[] }>(
      `/api/lookup/cities?q=${encodeURIComponent(q)}`,
    ),

  searchIata: (keyword: string) =>
    request<{ results: import('@/types').IataResult[] }>(
      `/api/lookup/iata?keyword=${encodeURIComponent(keyword)}`,
    ),

  exchangeRate: (from: string, to: string, amount: number) =>
    request<import('@/types').ExchangeResult>(
      `/api/lookup/exchange?from=${from}&to=${to}&amount=${amount}`,
    ),

  geocode: (address: string, city?: string) =>
    request<import('@/types').GeocodeResult>(
      `/api/lookup/geocode?address=${encodeURIComponent(address)}${city ? `&city=${encodeURIComponent(city)}` : ''}`,
    ),

  direction: (origin: string, destination: string, mode = 'walking') =>
    request<unknown>(
      `/api/lookup/direction?origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(destination)}&mode=${mode}`,
    ),

  // SSE — 通过 URL query param 传 token 认证（EventSource 不支持自定义 header）
  subscribeEvents: (tripId: string, onEvent: (event: string, data: Record<string, unknown>) => void, onError?: (err: Event) => void): EventSource => {
    loadTokens();
    // 只订阅后端实际发布的事件，避免死订阅
    const es = new EventSource(`${API_BASE}/api/trips/${tripId}/events?token=${encodeURIComponent(accessToken || '')}`);

    const handler = (eventType: string) => (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(eventType, data);
      } catch {
        onEvent(eventType, { raw: e.data });
      }
    };

    [
      'connected', 'profile_start', 'profile_complete',
      'agent_start', 'agent_complete',
      'recommend_start', 'recommend_plan_ready',
      'plan_start', 'plan_agent_start', 'plan_agent_complete', 'plan_ready',
      'planner_complete', 'planner_error',
    ].forEach((evt) => {
      es.addEventListener(evt, handler(evt));
    });

    es.onerror = (err) => {
      if (onError) onError(err);
    };

    return es;
  },
};
