'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSSE } from '@/hooks/useSSE';
import { User, Plane, Building2, MapPin, Route, Coins, ShieldCheck, Sparkles, ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';

/**
 * 第 4 幕：Agent 流水线可视化（对应后端 LangGraph 完整流程）
 * ProfileAgent → Flight∥Hotel∥POI 并行 → Itinerary→Budget→Constraint(回退≤3)
 * → Synthesizer
 *
 * - active：滚动到达第 4 幕时才显示并开始演示
 * - 传入 tripId：实时订阅 SSE，节点随事件点亮
 * - 无 tripId：演示模式，模拟依次点亮（展示产品如何工作）
 */
export function AgentPipeline({ tripId, active = true }: { tripId?: string; active?: boolean }) {
  const sse = useSSE(tripId || null);
  const [demoIdx, setDemoIdx] = useState(0);

  // 演示模式：滚动进入第 4 幕后逐节点点亮
  useEffect(() => {
    if (tripId) return;
    if (!active) { setDemoIdx(0); return; }
    setDemoIdx(0);
    const t = setInterval(() => {
      setDemoIdx((i) => {
        if (i >= NODES.length) { clearInterval(t); return i; }
        return i + 1;
      });
    }, 700);
    return () => clearInterval(t);
  }, [tripId, active]);

  // 由 SSE 事件映射节点状态
  const liveStatus: Record<string, 'done' | 'running'> = {};
  sse.stages.forEach((st) => {
    if (st.status === 'done') liveStatus[st.agent] = 'done';
    else if (st.status === 'running') liveStatus[st.agent] = 'running';
  });

  const NODES = [
    { key: 'ProfileAgent', name: '画像分析', icon: <User size={15} /> },
    { key: 'FlightAgent', name: '航班', icon: <Plane size={15} /> },
    { key: 'HotelAgent', name: '酒店', icon: <Building2 size={15} /> },
    { key: 'POIAgent', name: '景点', icon: <MapPin size={15} /> },
    { key: 'ItineraryAgent', name: '行程编排', icon: <Route size={15} /> },
    { key: 'BudgetAgent', name: '预算核算', icon: <Coins size={15} /> },
    { key: 'ConstraintAgent', name: '约束校验', icon: <ShieldCheck size={15} /> },
    { key: 'Synthesizer', name: '方案合成', icon: <Sparkles size={15} /> },
  ];

  const nodeState = (i: number) => {
    const key = NODES[i].key;
    if (tripId) {
      if (sse.error) return i < demoIdx ? 'done' : '';
      const st = liveStatus[key];
      if (st === 'done') return 'done';
      if (st === 'running') return 'running';
      if (sse.completed) return 'done';
      return '';
    }
    return i < demoIdx ? 'done' : i === demoIdx ? 'running' : '';
  };

  const isComplete = tripId ? sse.completed && !sse.error : demoIdx >= NODES.length;
  const isDemoRunning = !tripId && active && demoIdx < NODES.length;

  return (
    <div className={`agent-pipeline ${active ? 'is-active' : ''}`}>
      <div className="pipeline-flow">
        {NODES.map((n, i) => {
          const st = nodeState(i);
          return (
            <div key={n.key} className="pipeline-step">
              <div className={`pipeline-node ${st ? `is-${st}` : ''}`}>
                <div className="node-icon">
                  {st === 'running' ? <Loader2 size={15} className="animate-spin" /> : st === 'done' ? <CheckCircle2 size={15} /> : n.icon}
                </div>
                <span className="node-name">{n.name}</span>
                <span className="node-meta">
                  {st === 'running' ? '工作中…' : st === 'done' ? '完成' : '等待中'}
                </span>
              </div>
              {i < NODES.length - 1 && <span className="pipeline-arrow">→</span>}
            </div>
          );
        })}
      </div>

      {/* 实时生成的方案（SSE recommend_plan_ready / plan_ready）——过滤未填充的 pending 占位方框 */}
      {sse.plans.filter((p) => p.title).length > 0 && (
        <div className="pipeline-plans">
          {sse.plans.filter((p) => p.title).map((p, i) => (
            <div key={i} className="pipeline-plan-chip">
              <CheckCircle2 size={15} color="#a8f0c8" />
              <span>{p.title}</span>
              <span style={{ opacity: 0.7 }}>{p.reason}</span>
            </div>
          ))}
        </div>
      )}

      <div className="pipeline-flourish">
        {isComplete && !sse.error && (
          <div className="done-badge">
            {tripId
              ? <><CheckCircle2 size={18} /> {sse.planCount} 套方案已就绪</>
              : <><Sparkles size={18} /> 3 套差异化方案 · 每条附 10 字理由</>}
          </div>
        )}
        {sse.error && <div className="done-badge" style={{ borderColor: 'rgba(255,120,120,0.6)', color: '#ffb3b3', background: 'rgba(255,90,90,0.14)' }}>规划失败</div>}

        <div className="cta-row">
          <Link href={tripId && isComplete && !sse.error ? `/trips/${tripId}/select` : '/planner'} className="note-button">
            <span>{tripId && isComplete && !sse.error ? '选择方案' : '开始规划'} <ArrowRight size={18} /></span>
          </Link>
        </div>
      </div>
    </div>
  );
}
