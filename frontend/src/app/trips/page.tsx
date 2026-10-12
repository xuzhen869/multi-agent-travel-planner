'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import type { TripListItem } from '@/types';
import { formatCurrency, formatDateFull } from '@/lib/utils';
import { Loader2, Plus, MapPin, Clock, Trash2 } from 'lucide-react';

export default function TripsPage() {
  const [trips, setTrips] = useState<TripListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTrips = async () => {
    try {
      setTrips(await api.listTrips());
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { loadTrips(); }, []);

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除此行程？')) return;
    try { await api.deleteTrip(id); setTrips(t => t.filter(tr => tr.id !== id)); }
    catch { alert('删除失败'); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
    </div>
  );

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">我的行程</h1>
          <p className="text-sm text-gray-500 mt-1">{trips.length} 个行程</p>
        </div>
        <Link href="/planner" className="flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white font-medium hover:bg-indigo-700 transition-colors">
          <Plus className="h-4 w-4" /> 新建行程
        </Link>
      </div>

      {trips.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 p-12 text-center">
          <MapPin className="mx-auto h-10 w-10 text-gray-300 mb-3" />
          <p className="text-gray-500">还没有行程</p>
          <Link href="/planner" className="mt-3 inline-block text-indigo-600 hover:underline font-medium">开始你的第一次规划</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {trips.map(trip => (
            <div key={trip.id} className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-4 hover:border-indigo-200 transition-colors">
              <Link href={`/trips/${trip.id}`} className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-semibold text-gray-900 truncate">{trip.title || trip.destination || '未命名行程'}</h3>
                  {trip.status === 'completed' ? (
                    <span className="rounded-full bg-green-50 px-2 py-0.5 text-xs text-green-600 font-medium">已完成</span>
                  ) : trip.status === 'recommending' || trip.status === 'planning' ? (
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-600 font-medium">规划中</span>
                  ) : trip.status === 'draft' ? (
                    <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs text-red-600 font-medium">已失败</span>
                  ) : null}
                </div>
                <div className="mt-1 flex items-center gap-3 text-xs text-gray-500">
                  {trip.user_profile_label && <span>{trip.user_profile_label}</span>}
                  <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {formatDateFull(trip.created_at)}</span>
                  {trip.budget_total != null && <span>{formatCurrency(trip.budget_total, trip.budget_currency || 'CNY')}</span>}
                </div>
              </Link>
              <button onClick={(e) => { e.preventDefault(); handleDelete(trip.id); }}
                className="ml-4 rounded-lg p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors">
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
