// ====== 用户 ======
export interface User {
  id: string;
  email: string;
  display_name: string | null;
  oauth_provider: string | null;
  is_first_time: boolean;
  created_at: string;
}

export interface Traveler {
  age: number;
  type: 'adult' | 'child' | 'senior';
}

export interface Preference {
  default_departure_city: string | null;
  preferred_hotel_star: number;
  preferred_flight_class: string;
  pace: string;
  interests: string[];
  dietary: string[];
  budget_default_currency: string;
  default_travelers: Traveler[];
  is_first_time: boolean;
}

export interface UserProfile {
  label: string | null;
  traits: string[];
  budget_flexibility: string | null;
  generated_at: string | null;
}

// ====== 行程 ======
export interface TripCreateRequest {
  destination: string;
  departure_city: string;
  start_date: string;
  end_date: string;
  travelers: Traveler[];
  budget: { total: number; currency: string };
  preferences: Record<string, unknown>;
  mode: 'recommend' | 'direct';
}

export interface TripListItem {
  id: string;
  title: string | null;
  destination: string | null;
  status: string;
  mode: string;
  selected_plan_id: string | null;
  budget_total: number | null;
  budget_currency: string | null;
  user_profile_label: string | null;
  created_at: string;
}

export interface PlanCard {
  id: string;
  title: string;
  reason: string;
  total_cost: number;
  budget_breakdown: Record<string, number>;
  itinerary: Itinerary;
  highlights: string[];
}

export interface TripDetail {
  id: string;
  title: string | null;
  status: string;
  mode: string;
  request_params: Record<string, unknown>;
  recommendations: PlanCard[] | null;
  selected_plan_id: string | null;
  plan_data: PlanCard | null;
  user_profile: Record<string, unknown> | null;
  weather: WeatherDay[] | null;
  budget_total: number | null;
  budget_currency: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlanCreatedResponse {
  trip_id: string;
  status: string;
  events_url: string;
}

// ====== 天气 ======
export interface WeatherDay {
  date: string;
  temp_min: number;
  temp_max: number;
  temp_avg: number;
  main_weather: string;
  humidity_avg: number;
}

// ====== 行程数据 ======
export interface ItineraryDay {
  date: string;
  label: string;
  flight_inbound?: Record<string, unknown>;
  hotel_checkin?: Record<string, unknown>;
  activities: Activity[];
  transport: Transport[];
  day_budget_estimate: number;
}

export interface Activity {
  time: string;
  type: 'checkin' | 'attraction' | 'dinner' | 'lunch' | 'breakfast' | 'transport';
  name: string;
  poi_id?: string;
  duration_min?: number;
  notes?: string;
}

export interface Transport {
  from: string;
  to: string;
  mode: string;
  duration_min: number;
  estimated_cost: number;
}

export interface Itinerary {
  days: ItineraryDay[];
}

// ====== SSE 事件 ======
export interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

// ====== 认证 ======
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_at: string;
}

// ====== 辅助查询（lookup） ======
export interface CityOption {
  city: string;
  region: string;
  iata?: string;
}

export interface IataResult {
  city: string;
  iata: string;
  airport?: string;
}

export interface ExchangeResult {
  from: string;
  to: string;
  amount: number;
  result: number;
  rate: number;
}

export interface GeocodeResult {
  location?: { lng: number; lat: number };
  error?: string;
}

export interface OAuthUrlResult {
  url: string | null;
  error?: string;
}
