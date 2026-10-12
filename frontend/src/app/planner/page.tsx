'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ArrowRight, MapPin, Calendar, Users, Coins, Search, RefreshCw } from 'lucide-react';
import type { Traveler } from '@/types';

type TravelerType = Traveler['type'];

interface CityOption {
  city: string;
  region: string;
  iata?: string;
}

const DEBOUNCE_MS = 300;

export default function PlannerPage() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState({
    destination: '',
    departure_city: '上海',
    start_date: '',
    end_date: '',
    travelers: [{ age: 30, type: 'adult' as TravelerType }],
    budget_total: 20000,
    budget_currency: 'CNY',
    preferences: {},
  });

  // 城市搜索（lookup /cities）
  const [cityQuery, setCityQuery] = useState('');
  const [cityTarget, setCityTarget] = useState<'departure' | 'destination'>('destination');
  const [cityResults, setCityResults] = useState<CityOption[]>([]);
  const [cityOpen, setCityOpen] = useState(false);
  const [searchingCity, setSearchingCity] = useState(false);
  const cityBoxRef = useRef<HTMLDivElement>(null);

  // 汇率换算（lookup /exchange）
  const [exOpen, setExOpen] = useState(false);
  const [exFrom, setExFrom] = useState('CNY');
  const [exTo, setExTo] = useState('JPY');
  const [exAmount, setExAmount] = useState(1000);
  const [exResult, setExResult] = useState<{ result: number; rate: number } | null>(null);
  const [exBusy, setExBusy] = useState(false);

  // 合并已保存的旅行偏好作为个性化规划的初始输入（用户可覆盖）
  useEffect(() => {
    (async () => {
      try {
        const p = await api.getPreferences();
        setForm(f => ({
          ...f,
          departure_city: p.default_departure_city || f.departure_city,
          travelers: p.default_travelers?.length ? p.default_travelers : f.travelers,
          budget_currency: p.budget_default_currency || f.budget_currency,
          preferences: {
            hotel_star: p.preferred_hotel_star,
            flight_class: p.preferred_flight_class,
            pace: p.pace,
            interests: p.interests,
            dietary: p.dietary,
          },
        }));
      } catch { /* 未登录或读取失败则保持默认 */ }
    })();
  }, []);

  // 点击外部关闭城市下拉
  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (cityBoxRef.current && !cityBoxRef.current.contains(e.target as Node)) setCityOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  // 城市搜索防抖
  useEffect(() => {
    if (!cityOpen) return;
    const q = cityQuery.trim();
    if (!q) { setCityResults([]); return; }
    setSearchingCity(true);
    const t = setTimeout(async () => {
      try {
        const res = await api.searchCities(q);
        setCityResults(res.cities || []);
      } catch {
        setCityResults([]);
      } finally {
        setSearchingCity(false);
      }
    }, DEBOUNCE_MS);
    return () => clearTimeout(t);
  }, [cityQuery, cityOpen]);

  const update = (k: string, v: unknown) => setForm(f => ({ ...f, [k]: v }));

  const openCitySearch = (target: 'departure' | 'destination', initial: string) => {
    setCityTarget(target);
    setCityQuery(initial);
    setCityOpen(true);
  };

  const pickCity = (opt: CityOption) => {
    if (cityTarget === 'departure') {
      update('departure_city', opt.city + (opt.iata ? ` (${opt.iata})` : ''));
    } else {
      update('destination', opt.city + (opt.iata ? ` (${opt.iata})` : ''));
    }
    setCityOpen(false);
  };

  const handleExchange = async () => {
    if (!exAmount || exAmount <= 0) return;
    setExBusy(true);
    try {
      const res = await api.exchangeRate(exFrom, exTo, exAmount);
      setExResult({ result: res.result, rate: res.rate });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '汇率查询失败');
      setExResult(null);
    } finally {
      setExBusy(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const res = await api.createTrip({
        destination: form.destination,
        departure_city: form.departure_city,
        start_date: form.start_date,
        end_date: form.end_date,
        travelers: form.travelers,
        budget: { total: form.budget_total, currency: form.budget_currency },
        preferences: form.preferences,
        mode: 'recommend',
      });
      router.push(`/trips/${res.trip_id}/progress`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg px-4 py-12">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">规划新行程</h1>
        <p className="mt-1 text-gray-500">AI 将分析你的偏好，推荐 2-3 套方案</p>
      </div>

      {error && <div className="mb-6 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1"><MapPin className="h-3.5 w-3.5" /> 出发地</label>
            <input type="text" value={form.departure_city} onClick={() => openCitySearch('departure', form.departure_city)}
              onChange={e => update('departure_city', e.target.value)} required
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1"><MapPin className="h-3.5 w-3.5" /> 目的地</label>
            <input type="text" value={form.destination} onClick={() => openCitySearch('destination', form.destination)}
              onChange={e => update('destination', e.target.value)} required
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="如：东京" />
          </div>
        </div>

        {/* 城市搜索下拉（lookup /cities） */}
        {cityOpen && (
          <div ref={cityBoxRef} className="rounded-lg border border-gray-200 bg-white shadow-lg overflow-hidden">
            <div className="flex items-center gap-2 border-b border-gray-100 px-3 py-2">
              <Search className="h-4 w-4 text-gray-400" />
              <input
                autoFocus
                type="text"
                value={cityQuery}
                onChange={e => setCityQuery(e.target.value)}
                placeholder="输入城市名或 IATA 码搜索…"
                className="flex-1 text-sm focus:outline-none"
              />
              {searchingCity && <RefreshCw className="h-3.5 w-3.5 animate-spin text-gray-300" />}
            </div>
            <div className="max-h-56 overflow-y-auto">
              {cityResults.length === 0 && !searchingCity && (
                <p className="px-3 py-3 text-sm text-gray-400">输入关键词搜索城市</p>
              )}
              {cityResults.map((c, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => pickCity(c)}
                  className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-indigo-50 transition-colors"
                >
                  <span className="text-gray-800">{c.city}</span>
                  <span className="flex items-center gap-2 text-xs text-gray-400">
                    {c.region}
                    {c.iata && <span className="rounded bg-gray-100 px-1.5 py-0.5 font-mono text-gray-500">{c.iata}</span>}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1"><Calendar className="h-3.5 w-3.5" /> 出发日期</label>
            <input type="date" value={form.start_date} onChange={e => update('start_date', e.target.value)} required
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </div>
          <div>
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1"><Calendar className="h-3.5 w-3.5" /> 返回日期</label>
            <input type="date" value={form.end_date} onChange={e => update('end_date', e.target.value)} required
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
          </div>
        </div>

        <div>
          <label className="flex items-center gap-1 text-sm font-medium text-gray-700 mb-1"><Users className="h-3.5 w-3.5" /> 出行人</label>
          {form.travelers.map((t, i) => (
            <div key={i} className="flex items-center gap-2 mb-2">
              <select value={t.type} onChange={e => {
                const arr = [...form.travelers]; arr[i] = { ...arr[i], type: e.target.value as TravelerType }; update('travelers', arr);
              }} className="rounded-lg border border-gray-300 px-3 py-2 text-sm">
                <option value="adult">成人</option><option value="child">儿童</option><option value="senior">老人</option>
              </select>
              <input type="number" value={t.age} onChange={e => {
                const arr = [...form.travelers]; arr[i] = { ...arr[i], age: parseInt(e.target.value) || 0 }; update('travelers', arr);
              }} className="w-20 rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="年龄" />
              {form.travelers.length > 1 && (
                <button type="button" onClick={() => update('travelers', form.travelers.filter((_, j) => j !== i))} className="text-red-400 text-sm">移除</button>
              )}
            </div>
          ))}
          <button type="button" onClick={() => update('travelers', [...form.travelers, { age: 30, type: 'adult' as TravelerType }])} className="text-sm text-indigo-600 hover:underline">+ 添加</button>
        </div>

        {/* 预算 + 汇率换算工具 */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="flex items-center gap-1 text-sm font-medium text-gray-700"><Coins className="h-3.5 w-3.5" /> 总预算 ({form.budget_currency})</label>
            <button type="button" onClick={() => setExOpen(o => !o)}
              className="flex items-center gap-1 text-xs text-indigo-600 hover:underline">
              <RefreshCw className="h-3 w-3" /> 汇率换算
            </button>
          </div>
          <div className="flex gap-2">
            <input type="number" value={form.budget_total} onChange={e => update('budget_total', parseInt(e.target.value) || 0)}
              className="flex-1 rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
            <select value={form.budget_currency} onChange={e => update('budget_currency', e.target.value)}
              className="rounded-lg border border-gray-300 px-3 py-2.5 text-sm">
              {['CNY', 'USD', 'JPY', 'EUR', 'HKD', 'KRW', 'THB', 'SGD'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>

          {exOpen && (
            <div className="mt-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <p className="text-xs font-medium text-gray-600 mb-2">汇率换算（lookup /exchange）</p>
              <div className="flex items-center gap-2 text-sm">
                <select value={exFrom} onChange={e => setExFrom(e.target.value)} className="rounded-lg border border-gray-300 px-2 py-1.5">
                  {['CNY', 'USD', 'JPY', 'EUR', 'HKD', 'KRW', 'THB', 'SGD'].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <span className="text-gray-400">→</span>
                <select value={exTo} onChange={e => setExTo(e.target.value)} className="rounded-lg border border-gray-300 px-2 py-1.5">
                  {['CNY', 'USD', 'JPY', 'EUR', 'HKD', 'KRW', 'THB', 'SGD'].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
                <input type="number" value={exAmount} min={1} onChange={e => setExAmount(parseFloat(e.target.value) || 0)}
                  className="w-24 rounded-lg border border-gray-300 px-2 py-1.5" placeholder="金额" />
                <button type="button" onClick={handleExchange} disabled={exBusy}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:opacity-50">
                  {exBusy ? '换算中…' : '换算'}
                </button>
              </div>
              {exResult && (
                <p className="mt-2 text-sm text-gray-700">
                  {exAmount.toLocaleString()} {exFrom} = <span className="font-semibold text-indigo-600">{exResult.result.toLocaleString()} {exTo}</span>
                  <span className="ml-2 text-xs text-gray-400">（1 {exFrom} ≈ {exResult.rate.toFixed(6)} {exTo}）</span>
                </p>
              )}
            </div>
          )}
        </div>

        <button type="submit" disabled={submitting}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 py-3 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {submitting ? '正在创建...' : <>{' '}开始智能规划 <ArrowRight className="h-4 w-4" /></>}
        </button>
      </form>
    </div>
  );
}
