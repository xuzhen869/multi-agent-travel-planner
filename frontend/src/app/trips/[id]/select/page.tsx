'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import type { TripDetail, PlanCard } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { Sparkles, Zap, Banknote, Coffee, Camera, Map } from 'lucide-react';
import { Loader2 } from 'lucide-react';

export default function SelectPlanPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = params.id as string;
  const [trip, setTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const t = await api.getTrip(tripId);
        setTrip(t);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : '加载失败');
      } finally {
        setLoading(false);
      }
    })();
  }, [tripId]);

  const handleSelect = async (planId: string) => {
    setSelecting(planId);
    try {
      await api.selectPlan(tripId, planId);
      router.push(`/trips/${tripId}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '选择失败');
      setSelecting(null);
    }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
    </div>
  );

  if (error) return (
    <div className="mx-auto max-w-lg px-4 py-20 text-center">
      <p className="text-red-500">{error}</p>
      <button onClick={() => router.push('/planner')} className="mt-4 text-indigo-600 hover:underline">重新规划</button>
    </div>
  );

  const plans = trip?.recommendations || [];
  const profileLabel = trip?.user_profile && typeof trip.user_profile === 'object' && 'label' in trip.user_profile ? (trip.user_profile as Record<string,unknown>).label as string : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="mb-10 text-center">
        {profileLabel && (
          <div className="mb-3 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-4 py-1.5 text-sm text-indigo-600">
            <Sparkles className="h-3.5 w-3.5" /> {profileLabel}
          </div>
        )}
        <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">选择你的旅行方案</h1>
        <p className="mt-2 text-gray-500">AI 为你的偏好生成了 {plans.length} 套差异化方案</p>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {plans.map((plan: PlanCard) => (
          <div key={plan.id}
            className="relative flex flex-col rounded-2xl border border-gray-200 bg-white p-6 shadow-sm hover:shadow-md hover:border-indigo-200 transition-all">
            <div className="mb-4">
              <h3 className="text-lg font-bold text-gray-900">{plan.title}</h3>
              <span className="inline-block mt-1.5 rounded-full bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
                {plan.reason}
              </span>
            </div>

            <div className="mb-4 text-2xl font-bold text-indigo-600">
              {formatCurrency(plan.total_cost ?? 0)}
              <span className="text-sm font-normal text-gray-400"> / 全程</span>
            </div>

            {/* Highlights */}
            <div className="mb-4 flex-1 space-y-2">
              {plan.highlights?.slice(0, 3).map((h: string, i: number) => (
                <div key={i} className="flex items-start gap-2 text-sm text-gray-600">
                  {i === 0 && <Camera className="mt-0.5 h-3.5 w-3.5 text-gray-400 shrink-0" />}
                  {i === 1 && <Coffee className="mt-0.5 h-3.5 w-3.5 text-gray-400 shrink-0" />}
                  {i === 2 && <Map className="mt-0.5 h-3.5 w-3.5 text-gray-400 shrink-0" />}
                  <span>{h}</span>
                </div>
              ))}
            </div>

            {/* Budget breakdown mini */}
            {plan.budget_breakdown && (
              <div className="mb-4 border-t border-gray-100 pt-3">
                <div className="flex items-center gap-1 text-xs text-gray-500 mb-2"><Banknote className="h-3 w-3" /> 费用概览</div>
                <div className="space-y-1">
                  {Object.entries(plan.budget_breakdown).slice(0, 4).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs text-gray-500">
                      <span>{k}</span>
                      <span className="font-medium text-gray-700">{formatCurrency(v as number)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => handleSelect(plan.id)}
              disabled={selecting !== null}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-indigo-600 py-2.5 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
              {selecting === plan.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
              {selecting === plan.id ? '选择中...' : '选这个'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
