'use client';

import { Loader2, CheckCircle2, Circle, Banknote } from 'lucide-react';
import type { PlanProgress, PlanStep } from '@/hooks/useSSE';
import { formatCurrency } from '@/lib/utils';

/**
 * 方案进度方框 — 单个方案一个方框，内部 4 步 Agent 步骤流（数据采集→编排行程→核算预算→约束校验），
 * 步骤随 SSE 事件逐个点亮，方案就绪后展示标题与预算价格。
 */
export function PlanProgressCard({ plan, index }: { plan: PlanProgress; index: number }) {
  const isPending = plan.status === 'pending';
  const isReady = plan.status === 'ready';

  return (
    <div
      className={`relative flex flex-col rounded-2xl border p-5 shadow-sm transition-all ${
        isReady
          ? 'border-green-200 bg-white'
          : isPending
            ? 'border-dashed border-gray-200 bg-gray-50'
            : 'border-indigo-200 bg-white'
      }`}
    >
      {/* 头部：序号 + 标题 + 状态徽章 */}
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-gray-400">方案 {index + 1}</p>
          {plan.title ? (
            <h3 className="mt-0.5 truncate text-lg font-bold text-gray-900">{plan.title}</h3>
          ) : (
            <h3 className="mt-0.5 text-lg font-semibold text-gray-300">
              {isPending ? '等待生成...' : '生成中...'}
            </h3>
          )}
        </div>
        <span
          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-medium ${
            isReady
              ? 'bg-green-50 text-green-700'
              : isPending
                ? 'bg-gray-100 text-gray-400'
                : 'bg-indigo-50 text-indigo-600'
          }`}
        >
          {isReady ? '已就绪' : isPending ? '等待中' : '生成中'}
        </span>
      </div>

      {/* Agent 步骤流 */}
      <div className="mb-4 space-y-2.5">
        {plan.steps.map((st) => (
          <PlanStepRow key={st.key} step={st} />
        ))}
      </div>

      {/* 底部：就绪显示预算价格 */}
      {isReady && (
        <div className="flex items-center justify-between border-t border-gray-100 pt-3">
          <div className="flex items-center gap-1.5 text-sm text-gray-500">
            <Banknote className="h-4 w-4 text-gray-400" />
            全程预算
          </div>
          <div className="text-xl font-bold text-indigo-600">
            {plan.cost != null ? formatCurrency(plan.cost) : '—'}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanStepRow({ step }: { step: PlanStep }) {
  const icon =
    step.status === 'done' ? (
      <CheckCircle2 className="h-4 w-4 text-green-500" />
    ) : step.status === 'running' ? (
      <Loader2 className="h-4 w-4 animate-spin text-indigo-500" />
    ) : (
      <Circle className="h-4 w-4 text-gray-300" />
    );

  return (
    <div className="flex items-center gap-2.5">
      <div className="flex h-6 w-6 shrink-0 items-center justify-center">{icon}</div>
      <span className={`text-sm ${step.status === 'waiting' ? 'text-gray-400' : 'text-gray-700'}`}>
        {step.name}
      </span>
      {step.message && step.status !== 'waiting' && (
        <span className="ml-auto truncate text-xs text-gray-400">{step.message}</span>
      )}
    </div>
  );
}
