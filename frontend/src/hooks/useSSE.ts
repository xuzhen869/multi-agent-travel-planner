'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '@/lib/api';

/** 方案方框内单个 Agent 步骤 */
export interface PlanStep {
  key: 'data' | 'itinerary' | 'budget' | 'constraint';
  name: string;
  status: 'waiting' | 'running' | 'done';
  message: string;
}

/** 方案进度方框 */
export interface PlanProgress {
  plan_id: string;
  title: string;
  reason: string;
  cost: number | null;
  status: 'pending' | 'running' | 'ready';
  steps: PlanStep[];
}

/** 方框内固定 4 步（顺序即展示顺序） */
const PLAN_STEP_DEFS: { key: PlanStep['key']; name: string }[] = [
  { key: 'data', name: '数据采集' },
  { key: 'itinerary', name: '编排行程' },
  { key: 'budget', name: '核算预算' },
  { key: 'constraint', name: '约束校验' },
];

function makePlanSteps(): PlanStep[] {
  return PLAN_STEP_DEFS.map((s) => ({ ...s, status: 'waiting', message: '' }));
}

interface SSEState {
  connected: boolean;
  mode: string | null;
  profileLabel: string | null;
  stages: { agent: string; status: string; message: string }[];
  plans: PlanProgress[];
  planCount: number;
  error: string | null;
  completed: boolean;
}

/**
 * 订阅规划实时进度。
 * stages/plans 以 ref 为唯一状态源（避免并发事件下 state 闭包丢失更新），
 * setState 只做快照派生；connected 事件的 snapshot 用于恢复订阅前已发生的进度。
 */
export function useSSE(tripId: string | null) {
  const [state, setState] = useState<SSEState>({
    connected: false,
    mode: null,
    profileLabel: null,
    stages: [],
    plans: [],
    planCount: 0,
    error: null,
    completed: false,
  });
  const esRef = useRef<EventSource | null>(null);
  const stagesRef = useRef<SSEState['stages']>([]);
  const plansRef = useRef<SSEState['plans']>([]);
  const dataCollectedRef = useRef(false); // 全局数据采集（Flight/Hotel/POI）是否已完成

  const syncStages = useCallback(() => {
    setState(s => ({ ...s, stages: [...stagesRef.current] }));
  }, []);

  const syncPlans = useCallback(() => {
    setState(s => ({ ...s, plans: [...plansRef.current] }));
  }, []);

  const handleEvent = useCallback((event: string, data: Record<string, unknown>) => {
    switch (event) {
      case 'connected': {
        const snap = data.snapshot as Record<string, unknown> | undefined;
        if (snap) {
          // 补发快照：恢复订阅建立前已发生的进度
          const snapStatus = snap.status as string;
          setState(s => ({
            ...s,
            connected: true,
            error: null, // 重连成功，清除之前的连接中断标记
            mode: (snap.mode as string) || s.mode,
            planCount: (snap.plan_count as number) || 0,
            profileLabel: (snap.profile_label as string) || s.profileLabel,
            completed: s.completed || snapStatus === 'completed' || Boolean(snap.completed_at),
          }));
        } else {
          setState(s => ({ ...s, connected: true, error: null }));
        }
        break;
      }

      case 'profile_start':
        stagesRef.current = [
          ...stagesRef.current,
          { agent: 'ProfileAgent', status: 'running', message: data.message as string },
        ];
        syncStages();
        break;

      case 'profile_complete':
        stagesRef.current = stagesRef.current.map(st =>
          st.agent === 'ProfileAgent' ? { ...st, status: 'done' } : st,
        );
        syncStages();
        setState(s => ({ ...s, profileLabel: (data.label as string) || s.profileLabel }));
        break;

      case 'agent_start':
        stagesRef.current = [
          ...stagesRef.current,
          { agent: data.agent as string, status: 'running', message: data.message as string },
        ];
        syncStages();
        break;

      case 'agent_complete':
        stagesRef.current = stagesRef.current.map(st =>
          st.agent === data.agent ? { ...st, status: 'done' } : st,
        );
        syncStages();

        // 数据采集 Agent 完成 → 所有方案方框的"数据采集"步骤标记完成
        if (['FlightAgent', 'HotelAgent', 'POIAgent'].includes(data.agent as string)) {
          dataCollectedRef.current = true;
          plansRef.current = plansRef.current.map((p) => ({
            ...p,
            steps: p.steps.map((st) =>
              st.key === 'data' ? { ...st, status: 'done', message: '数据采集完成' } : st,
            ),
          }));
          syncPlans();
        }
        break;

      case 'recommend_start': {
        const total = (data.total as number) || 0;
        // 预留 total 个空方框（pending 占位），等待 plan_start 逐个填充
        if (total > 0 && plansRef.current.length === 0) {
          plansRef.current = Array.from({ length: total }, (): PlanProgress => ({
            plan_id: '',
            title: '',
            reason: '',
            cost: null,
            status: 'pending',
            steps: makePlanSteps(),
          }));
          syncPlans();
        }
        setState(s => ({ ...s, planCount: total }));
        break;
      }

      case 'plan_start': {
        const planId = data.plan_id as string;
        const title = (data.title as string) || '';
        const reason = (data.reason as string) || '';
        const steps = makePlanSteps();
        // 若全局数据采集已完成，填充时直接点亮第一步
        if (dataCollectedRef.current) steps[0] = { ...steps[0], status: 'done', message: '数据采集完成' };
        // 优先填充预留的空方框，无空位则追加
        const emptyIdx = plansRef.current.findIndex(p => p.plan_id === '');
        if (emptyIdx >= 0) {
          plansRef.current[emptyIdx] = { plan_id: planId, title, reason, cost: null, status: 'running', steps };
        } else {
          plansRef.current.push({ plan_id: planId, title, reason, cost: null, status: 'running', steps });
        }
        syncPlans();
        break;
      }

      case 'plan_agent_start':
      case 'plan_agent_complete': {
        const planId = data.plan_id as string;
        const stepKey = data.step as PlanStep['key'];
        const isStart = event === 'plan_agent_start';
        plansRef.current = plansRef.current.map(p => {
          if (p.plan_id !== planId) return p;
          return {
            ...p,
            steps: p.steps.map(st =>
              st.key === stepKey
                ? { ...st, status: isStart ? 'running' : 'done', message: (data.message as string) || st.message }
                : st,
            ),
          };
        });
        syncPlans();
        break;
      }

      case 'plan_ready': {
        const planId = data.plan_id as string;
        plansRef.current = plansRef.current.map(p => {
          if (p.plan_id !== planId) return p;
          return {
            ...p,
            title: (data.title as string) || p.title,
            reason: (data.reason as string) || p.reason,
            cost: data.cost as number | null,
            status: 'ready',
            steps: p.steps.map(st => ({ ...st, status: 'done' })),
          };
        });
        syncPlans();
        break;
      }

      case 'recommend_plan_ready': {
        const planId = data.plan_id as string;
        // 向后兼容：旧后端无 plan_start/plan_ready 时，直接创建已就绪方框
        if (!plansRef.current.some(p => p.plan_id === planId)) {
          plansRef.current = [
            ...plansRef.current,
            {
              plan_id: planId,
              title: (data.title as string) || '',
              reason: (data.reason as string) || '',
              cost: null,
              status: 'ready',
              steps: makePlanSteps().map(st => ({ ...st, status: 'done' })),
            },
          ];
          syncPlans();
        }
        break;
      }

      case 'planner_complete':
        setState(s => ({ ...s, planCount: (data.plan_count as number) || 0, completed: true }));
        break;

      case 'planner_error':
        setState(s => ({ ...s, error: (data.message as string) || '规划失败', completed: true }));
        break;
    }
  }, [syncStages, syncPlans]);

  useEffect(() => {
    if (!tripId) return;

    const es = api.subscribeEvents(
      tripId,
      handleEvent,
      // 连接中断 ≠ 规划失败：EventSource 会自动重连，重连成功后
      // 'connected' 事件会清除 error。这里只标记未连接，避免误报"规划失败"。
      () => setState(s => ({ ...s, connected: false })),
    );

    esRef.current = es;

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [tripId, handleEvent]);

  return state;
}
