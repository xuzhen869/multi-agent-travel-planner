'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useSSE } from '@/hooks/useSSE';
import { Loader2, Sparkles, AlertCircle } from 'lucide-react';
import { PlanProgressCard } from '@/components/trips/PlanProgressCard';

export default function ProgressPage() {
  const params = useParams();
  const router = useRouter();
  const tripId = params.id as string;
  const sse = useSSE(tripId);

  useEffect(() => {
    if (sse.completed && !sse.error) {
      // direct 模式：唯一方案已自动选定 → 直接进详情页；recommend → 去选择页
      const target = sse.mode === 'direct' ? `/trips/${tripId}` : `/trips/${tripId}/select`;
      const timer = setTimeout(() => router.push(target), 800);
      return () => clearTimeout(timer);
    }
  }, [sse.completed, sse.error, sse.mode, tripId, router]);

  const hasPlans = sse.plans.length > 0;
  const readyCount = sse.plans.filter((p) => p.status === 'ready').length;
  const anyRunning = sse.plans.some((p) => p.status === 'running');

  return (
    <div className="mx-auto max-w-5xl px-4 py-12">
      <div className="mb-8 text-center">
        <h1 className="mb-2 text-xl font-bold text-gray-900">AI 正在为你规划行程</h1>
        <p className="text-sm text-gray-500">Multi-Agent 协作中，实时进度如下</p>
        {sse.profileLabel && (
          <div className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-indigo-50 px-4 py-1.5 text-sm text-indigo-600">
            <Sparkles className="h-3.5 w-3.5" /> {sse.profileLabel}
          </div>
        )}
      </div>

      {/* 方案方框网格：N 套方案 → N 个方框，方框内 Agent 步骤流式点亮 */}
      {hasPlans && (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {sse.plans.map((plan, i) => (
            <PlanProgressCard key={plan.plan_id || i} plan={plan} index={i} />
          ))}
        </div>
      )}

      {/* 已完成方案计数 */}
      {sse.planCount > 0 && (
        <p className="mt-6 text-center text-sm text-gray-500">
          已生成 {readyCount}/{sse.planCount} 套方案
        </p>
      )}

      {/* Error */}
      {sse.error && (
        <div className="mx-auto mt-8 max-w-lg rounded-xl bg-red-50 p-6 text-center">
          <AlertCircle className="mx-auto mb-2 h-8 w-8 text-red-400" />
          <p className="font-medium text-red-600">规划失败</p>
          <p className="mt-1 text-sm text-red-500">{sse.error}</p>
        </div>
      )}

      {/* 加载指示 */}
      {!sse.completed && !sse.error && (
        <div className="flex items-center justify-center gap-2 py-10 text-sm text-gray-400">
          <Loader2 className="h-4 w-4 animate-spin" />
          {hasPlans && anyRunning ? 'Agent 工作中...' : '正在连接...'}
        </div>
      )}

      {/* 完成提示 */}
      {sse.completed && !sse.error && (
        <p className="mt-6 animate-pulse text-center text-sm text-indigo-500">
          方案已就绪，正在跳转到选择页...
        </p>
      )}
    </div>
  );
}
