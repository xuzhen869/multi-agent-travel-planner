'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { ArrowRight, ArrowLeft, Check } from 'lucide-react';
import type { Traveler } from '@/types';

type TravelerType = Traveler['type'];

const INTERESTS = ['美食', '历史文化', '购物', '自然风光', '冒险', '艺术', '夜生活', '亲子', '温泉', '摄影'];
const PACES = [
  { value: 'relaxed', label: '轻松', desc: '每天 2 个主要活动，重在享受' },
  { value: 'moderate', label: '适中', desc: '每天 3 个活动，经典节奏' },
  { value: 'intensive', label: '紧凑', desc: '每天 4+ 个活动，充实打卡' },
];
const DIETARY = ['无限制', '素食', '忌海鲜', '清真', '无麸质'];

export default function OnboardingPage() {
  const { user, refreshUser } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [form, setForm] = useState({
    default_departure_city: '',
    default_travelers: [{ age: 30, type: 'adult' as TravelerType }],
    budget_default_currency: 'CNY',
    preferred_hotel_star: 4,
    preferred_flight_class: 'economy',
    pace: 'moderate',
    interests: [] as string[],
    dietary: [] as string[],
  });

  const update = (k: string, v: unknown) => setForm(f => ({ ...f, [k]: v }));

  const toggleArray = (arr: string[], item: string) =>
    arr.includes(item) ? arr.filter(i => i !== item) : [...arr, item];

  const handleSubmit = async () => {
    setSubmitting(true);
    setError('');
    try {
      await api.updatePreferences({
        ...form,
        default_travelers: form.default_travelers,
      });
      await refreshUser();
      router.push('/planner');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg px-4 py-12">
      {/* Progress bar */}
      <div className="mb-10 flex items-center gap-2">
        {[1, 2, 3].map(s => (
          <div key={s} className={`h-1.5 flex-1 rounded-full transition-colors ${s <= step ? 'bg-indigo-600' : 'bg-gray-200'}`} />
        ))}
      </div>

      {error && <div className="mb-6 rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}

      {/* Step 1: 基础信息 */}
      {step === 1 && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">基础信息</h2>
          <p className="text-gray-500">告诉我们你的出发城市和同行的人</p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">默认出发城市</label>
            <input type="text" value={form.default_departure_city} onChange={e => update('default_departure_city', e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="如：上海" />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">出行人</label>
            {form.default_travelers.map((t, i) => (
              <div key={i} className="flex items-center gap-3 mb-2">
                <select value={t.type} onChange={e => {
                  const arr = [...form.default_travelers];
                  arr[i] = { ...arr[i], type: e.target.value as TravelerType };
                  update('default_travelers', arr);
                }} className="rounded-lg border border-gray-300 px-3 py-2 text-sm">
                  <option value="adult">成人</option>
                  <option value="child">儿童</option>
                  <option value="senior">老人</option>
                </select>
                <input type="number" value={t.age} onChange={e => {
                  const arr = [...form.default_travelers];
                  arr[i] = { ...arr[i], age: parseInt(e.target.value) || 0 };
                  update('default_travelers', arr);
                }} className="w-20 rounded-lg border border-gray-300 px-3 py-2 text-sm" placeholder="年龄" />
                {form.default_travelers.length > 1 && (
                  <button onClick={() => update('default_travelers', form.default_travelers.filter((_, j) => j !== i))}
                    className="text-red-400 text-sm hover:text-red-600">移除</button>
                )}
              </div>
            ))}
            <button onClick={() => update('default_travelers', [...form.default_travelers, { age: 30, type: 'adult' as TravelerType }])}
              className="text-sm text-indigo-600 hover:underline">+ 添加出行人</button>
          </div>
        </div>
      )}

      {/* Step 2: 预算与节奏 */}
      {step === 2 && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">预算与节奏</h2>
          <p className="text-gray-500">设定你的旅行风格偏好</p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">酒店星级偏好</label>
            <div className="flex gap-2">
              {[1, 2, 3, 4, 5].map(s => (
                <button key={s} onClick={() => update('preferred_hotel_star', s)}
                  className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${form.preferred_hotel_star === s ? 'border-indigo-600 bg-indigo-50 text-indigo-600' : 'border-gray-200 text-gray-600 hover:border-gray-300'}`}>
                  {s} 星
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">舱位偏好</label>
            <div className="flex gap-2">
              {[
                { v: 'economy', l: '经济舱' },
                { v: 'business', l: '商务舱' },
                { v: 'first', l: '头等舱' },
              ].map(o => (
                <button key={o.v} onClick={() => update('preferred_flight_class', o.v)}
                  className={`flex-1 rounded-lg border py-2 text-sm font-medium transition-colors ${form.preferred_flight_class === o.v ? 'border-indigo-600 bg-indigo-50 text-indigo-600' : 'border-gray-200 text-gray-600 hover:border-gray-300'}`}>
                  {o.l}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">旅行节奏</label>
            <div className="space-y-2">
              {PACES.map(p => (
                <button key={p.value} onClick={() => update('pace', p.value)}
                  className={`w-full rounded-lg border px-4 py-3 text-left transition-colors ${form.pace === p.value ? 'border-indigo-600 bg-indigo-50' : 'border-gray-200 hover:border-gray-300'}`}>
                  <span className="font-medium text-gray-900">{p.label}</span>
                  <span className="ml-2 text-sm text-gray-500">{p.desc}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Step 3: 兴趣 */}
      {step === 3 && (
        <div className="space-y-6">
          <h2 className="text-2xl font-bold text-gray-900">兴趣偏好</h2>
          <p className="text-gray-500">选择你感兴趣的旅行主题</p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">兴趣标签（可多选）</label>
            <div className="flex flex-wrap gap-2">
              {INTERESTS.map(tag => (
                <button key={tag} onClick={() => update('interests', toggleArray(form.interests, tag))}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${form.interests.includes(tag) ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                  {tag}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">饮食限制</label>
            <div className="flex flex-wrap gap-2">
              {DIETARY.map(d => (
                <button key={d} onClick={() => update('dietary', toggleArray(form.dietary, d === '无限制' ? '无' : d))}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition-colors ${form.dietary.includes(d === '无限制' ? '无' : d) ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Navigation */}
      <div className="mt-10 flex items-center justify-between">
        {step > 1 ? (
          <button onClick={() => setStep(s => s - 1)} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
            <ArrowLeft className="h-4 w-4" /> 上一步
          </button>
        ) : <div />}

        {step < 3 ? (
          <button onClick={() => setStep(s => s + 1)} className="flex items-center gap-1 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm text-white font-medium hover:bg-indigo-700">
            下一步 <ArrowRight className="h-4 w-4" />
          </button>
        ) : (
          <button onClick={handleSubmit} disabled={submitting}
            className="flex items-center gap-1 rounded-lg bg-indigo-600 px-6 py-2.5 text-sm text-white font-medium hover:bg-indigo-700 disabled:opacity-50">
            {submitting ? '保存中...' : <><Check className="h-4 w-4" /> 完成设置，开始规划</>}
          </button>
        )}
      </div>
    </div>
  );
}
