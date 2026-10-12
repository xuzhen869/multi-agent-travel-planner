'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { TripDetail } from '@/types';
import { formatCurrency, formatDate } from '@/lib/utils';
import { Loader2, ArrowLeft, MapPin, Clock, Banknote, Coffee, Camera, Sun, Moon, Sunrise, Cloud, Thermometer, Droplets } from 'lucide-react';

const ACTIVITY_ICONS: Record<string, React.ReactNode> = {
  attraction: <Camera className="h-4 w-4 text-blue-500" />,
  dinner: <Moon className="h-4 w-4 text-purple-500" />,
  lunch: <Sun className="h-4 w-4 text-amber-500" />,
  breakfast: <Coffee className="h-4 w-4 text-orange-500" />,
  checkin: <MapPin className="h-4 w-4 text-green-500" />,
};

export default function TripDetailPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = params.id as string;
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try { setTrip(await api.getTrip(tripId)); } catch { /* ignore */ }
      finally { setLoading(false); }
    })();
  }, [tripId]);

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
    </div>
  );

  if (!trip) return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <p className="text-gray-500">行程未找到</p>
      <button onClick={() => router.push('/trips')} className="mt-4 text-indigo-600 hover:underline">返回列表</button>
    </div>
  );

  // 规划进行中 → 跳转到进度页
  if (trip.status === 'recommending' || trip.status === 'planning') {
    router.push(`/trips/${tripId}/progress`);
    return null;
  }

  // 规划失败或无方案 → 显示异常态而非空白页
  if (trip.status === 'draft' || !trip.plan_data) {
    return (
      <div className="mx-auto max-w-lg px-4 py-20 text-center">
        <p className="text-gray-500">该行程规划未完成或已失败</p>
        <div className="mt-4 flex justify-center gap-4">
          <button onClick={() => router.push(`/trips/${tripId}/progress`)} className="text-indigo-600 hover:underline">查看进度</button>
          <button
            onClick={() => api.regenerateTrip(tripId).then(() => router.push(`/trips/${tripId}/progress`))}
            className="text-indigo-600 hover:underline">
            重新规划
          </button>
        </div>
        <button onClick={() => router.push('/trips')} className="mt-4 text-gray-500 hover:underline">返回列表</button>
      </div>
    );
  }

  const plan = trip.plan_data;
  const itinerary = plan?.itinerary;
  const budget = plan?.budget_breakdown;

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <button onClick={() => router.push('/trips')} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft className="h-4 w-4" /> 返回列表
      </button>

      {trip.user_profile && typeof trip.user_profile === 'object' && 'label' in trip.user_profile && (
        <div className="mb-6 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-4 py-1.5 text-sm text-indigo-600">
          {(trip.user_profile as Record<string,unknown>).label as string}
        </div>
      )}

      <h1 className="text-2xl font-bold text-gray-900">{trip.title || '行程详情'}</h1>
      {plan && (
        <div className="mt-2 flex items-center gap-3 text-sm text-gray-500">
          {plan.title && <span className="font-medium text-indigo-600">{plan.title}</span>}
          {plan.reason && <span className="text-amber-600">&ldquo;{plan.reason}&rdquo;</span>}
          {plan.total_cost > 0 && <span className="flex items-center gap-1"><Banknote className="h-3.5 w-3.5" /> {formatCurrency(plan.total_cost)}</span>}
        </div>
      )}

      {/* Weather */}
      {trip.weather && trip.weather.length > 0 && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2"><Cloud className="h-5 w-5 text-sky-500" /> 天气预报</h2>
          <div className="flex gap-3 overflow-x-auto pb-2">
            {trip.weather.slice(0, 7).map((w, i) => (
              <div key={i} className="shrink-0 rounded-xl border border-gray-200 bg-white p-4 min-w-[110px] text-center">
                <p className="text-xs text-gray-500 mb-1">{formatDate(w.date)}</p>
                <Thermometer className="mx-auto h-5 w-5 text-orange-400 mb-1" />
                <p className="text-sm font-semibold text-gray-900">{w.temp_avg}°C</p>
                <p className="text-xs text-gray-500">{w.temp_min}° ~ {w.temp_max}°</p>
                <p className="text-xs text-gray-400 mt-1">{w.main_weather}</p>
                {w.humidity_avg != null && (
                  <p className="text-xs text-gray-400 flex items-center justify-center gap-1 mt-0.5">
                    <Droplets className="h-3 w-3" />{w.humidity_avg}%
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Day Timeline */}
      {itinerary?.days && itinerary.days.length > 0 && (
        <div className="mt-8 space-y-6">
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2"><Clock className="h-5 w-5 text-indigo-500" /> 每日行程</h2>
          {itinerary.days.map((day, i) => (
            <div key={i} className="rounded-xl border border-gray-200 bg-white overflow-hidden">
              <div className="bg-gray-50 px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-gray-900">{formatDate(day.date)}</span>
                  <span className="ml-2 text-sm text-gray-500">{day.label}</span>
                </div>
                {day.day_budget_estimate > 0 && (
                  <span className="text-sm text-gray-500">{formatCurrency(day.day_budget_estimate)}</span>
                )}
              </div>
              <div className="px-5 py-3 space-y-3">
                {day.activities.map((act, j) => (
                  <div key={j} className="flex items-start gap-3">
                    <div className="mt-0.5">{ACTIVITY_ICONS[act.type] || <MapPin className="h-4 w-4 text-gray-400" />}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400 font-mono">{act.time}</span>
                        <span className="text-sm font-medium text-gray-900">{act.name}</span>
                      </div>
                      {act.notes && <p className="text-xs text-gray-500 mt-0.5">{act.notes}</p>}
                    </div>
                    {act.duration_min && <span className="text-xs text-gray-400 shrink-0">{act.duration_min}分钟</span>}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Budget */}
      {budget && (
        <div className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2"><Banknote className="h-5 w-5 text-indigo-500" /> 费用明细</h2>
          <div className="rounded-xl border border-gray-200 bg-white p-5">
            <div className="space-y-2">
              {Object.entries(budget).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-gray-600 capitalize">{k.replace(/_/g, ' ')}</span>
                  <span className="font-medium text-gray-900">{formatCurrency(v as number)}</span>
                </div>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-100 flex justify-between font-semibold">
              <span className="text-gray-900">总计</span>
              <span className="text-indigo-600 text-lg">{formatCurrency(plan?.total_cost || 0)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
