'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { Preference, UserProfile } from '@/types';
import { Loader2, RefreshCw, User, Settings2 } from 'lucide-react';

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();
  const router = useRouter();
  const [pref, setPref] = useState<Preference | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const [p, pr] = await Promise.all([api.getPreferences(), api.getProfile().catch(() => null)]);
        setPref(p);
        setProfile(pr);
      } catch { /* ignore */ } finally { setLoading(false); }
    })();
  }, []);

  const handleSave = async () => {
    if (!pref) return;
    setSaving(true);
    try {
      await api.updatePreferences({
        default_departure_city: pref.default_departure_city,
        preferred_hotel_star: pref.preferred_hotel_star,
        preferred_flight_class: pref.preferred_flight_class,
        pace: pref.pace,
        interests: pref.interests,
        dietary: pref.dietary,
        budget_default_currency: pref.budget_default_currency,
        default_travelers: pref.default_travelers,
      });
      await refreshUser();
      setMsg('保存成功');
      setTimeout(() => setMsg(''), 2000);
    } catch { setMsg('保存失败'); }
    finally { setSaving(false); }
  };

  const handleRefreshProfile = async () => {
    setRefreshing(true);
    try {
      await api.refreshProfile();
      // 画像由 Celery 异步生成，轮询等待其落地（最多 ~10s）
      const before = profile?.generated_at ?? null;
      const deadline = Date.now() + 10000;
      let latest = await api.getProfile();
      while (Date.now() < deadline && (!latest.generated_at || latest.generated_at === before)) {
        await new Promise(r => setTimeout(r, 800));
        latest = await api.getProfile();
      }
      setProfile(latest);
      setMsg('画像已刷新');
      setTimeout(() => setMsg(''), 2000);
    } catch { setMsg('刷新失败'); }
    finally { setRefreshing(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
    </div>
  );

  if (!pref) return <p className="text-center py-20 text-gray-500">无法加载偏好</p>;

  return (
    <div className="mx-auto max-w-lg px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">偏好设置</h1>
      <p className="text-sm text-gray-500 mb-8">修改你的旅行偏好，AI 将据此推荐方案</p>

      {msg && <div className={`mb-4 rounded-lg p-3 text-sm ${msg.includes('失败') ? 'bg-red-50 text-red-600' : 'bg-green-50 text-green-600'}`}>{msg}</div>}

      {/* Profile card */}
      {profile?.label && (
        <div className="mb-8 rounded-xl bg-indigo-50 p-5 flex items-center justify-between">
          <div>
            <p className="text-xs text-indigo-500 font-medium">当前旅行人格</p>
            <p className="text-lg font-bold text-indigo-700 mt-1 flex items-center gap-2">
              <User className="h-5 w-5" /> {profile.label}
            </p>
            {profile.traits && profile.traits.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-2">
                {(profile.traits as string[]).map((t: string) => (
                  <span key={t} className="rounded-full bg-white px-2.5 py-0.5 text-xs text-indigo-600">{t}</span>
                ))}
              </div>
            )}
          </div>
          <button onClick={handleRefreshProfile} disabled={refreshing}
            className="rounded-lg bg-white p-2 text-indigo-500 hover:text-indigo-700 hover:bg-indigo-100 transition-colors">
            <RefreshCw className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      )}

      {/* Preferences form */}
      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">默认出发城市</label>
          <input type="text" value={pref.default_departure_city || ''}
            onChange={e => setPref({ ...pref, default_departure_city: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">酒店星级</label>
            <select value={pref.preferred_hotel_star} onChange={e => setPref({ ...pref, preferred_hotel_star: parseInt(e.target.value) })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm">
              {[1,2,3,4,5].map(s => <option key={s} value={s}>{s} 星</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">舱位</label>
            <select value={pref.preferred_flight_class} onChange={e => setPref({ ...pref, preferred_flight_class: e.target.value })}
              className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm">
              <option value="economy">经济舱</option>
              <option value="business">商务舱</option>
              <option value="first">头等舱</option>
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">旅行节奏</label>
          <select value={pref.pace} onChange={e => setPref({ ...pref, pace: e.target.value })}
            className="w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm">
            <option value="relaxed">轻松（每天 2 个活动）</option>
            <option value="moderate">适中（每天 3 个活动）</option>
            <option value="intensive">紧凑（每天 4+ 个活动）</option>
          </select>
        </div>

        <button onClick={handleSave} disabled={saving}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-indigo-600 py-2.5 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Settings2 className="h-4 w-4" />}
          {saving ? '保存中...' : '保存偏好'}
        </button>
      </div>
    </div>
  );
}
