'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

export interface SightCard {
  id: string;
  kicker: string;
  title: string;
  desc: string;
  status?: string;
  thumb?: string;
  pin?: string;
  href?: string;
}

/**
 * 无限循环滑轨（模板原逻辑，逐字还原）：
 * 3 组相同卡片克隆 → activeSight 从中间组开始 →
 * prev/next/卡片点击更新 → transitionend 越界 jump 瞬跳回中间组。
 *
 * 关键实现（对照模板）：
 * - jumpSightSlider(i): 加 .is-jumping 禁过渡 → 更新位移 → 双 rAF 移除
 * - normalizeSightSlider: 越界时 jump 回中间组，避免轨道空滑
 * - transitionend 只处理 track 自身的 transform（排除卡片 hover 冒泡）
 */
export function SightSlider({ cards, onSelect }: { cards: SightCard[]; onSelect?: (c: SightCard) => void }) {
    const trackRef = useRef<HTMLDivElement>(null);
    const [activeSight, setActiveSightState] = useState(0);
    const activeSightRef = useRef(0);
    const originalCount = cards.length;
    // 拖拽状态
    const dragRef = useRef({ startX: 0, startActive: 0, dragging: false, moved: false, cardW: 0, gap: 0 });

    // 组装克隆后的卡片序列（3 组 × 原始卡片）
    const cloneCards: (SightCard & { _sightIdx: number })[] = Array.from({ length: 3 }, (_, setIdx) =>
      cards.map((c, i) => ({ ...c, _sightIdx: setIdx * originalCount + i })),
    ).flat();

    // 写入 --sights-shift 与 .is-active
    const updateSightSlider = useCallback((idx: number) => {
      const track = trackRef.current;
      if (!track || !track.children[0]) return;
      const card = track.children[0] as HTMLElement;
      const cardWidth = card.offsetWidth;
      const gap = parseFloat(getComputedStyle(track).columnGap || '0');
      track.style.setProperty('--sights-shift', `${-(cardWidth + gap) * idx}px`);
      track.querySelectorAll('.sight-card').forEach((el, i) => {
        el.classList.toggle('is-active', i === idx);
      });
    }, []);

    const setActive = useCallback((i: number) => {
      activeSightRef.current = i;
      setActiveSightState(i);
      updateSightSlider(i);
    }, [updateSightSlider]);

    // jump：禁过渡 → 位移 → 双 rAF 恢复过渡
    const jumpSightSlider = useCallback((i: number) => {
      const track = trackRef.current;
      if (!track) return;
      track.classList.add('is-jumping');
      setActive(i);
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          track.classList.remove('is-jumping');
        });
      });
    }, [setActive]);

    // 归一化：越界 → jump 回中间组
    const normalizeSightSlider = useCallback(() => {
      const cur = activeSightRef.current;
      if (cur >= originalCount * 2) {
        jumpSightSlider(cur - originalCount);
      } else if (cur < originalCount) {
        jumpSightSlider(cur + originalCount);
      }
    }, [originalCount, jumpSightSlider]);

    // 初始：activeSight = originalCount（中间组）
    useEffect(() => {
      setActive(originalCount);
    }, [originalCount, setActive]);

    // transitionend：仅 track 自身 transform（排除卡片 hover 冒泡）
    useEffect(() => {
      const track = trackRef.current;
      if (!track) return;
      const onTransitionEnd = (e: TransitionEvent) => {
        if (e.target !== track) return;
        if (e.propertyName !== 'transform') return;
        normalizeSightSlider();
      };
      track.addEventListener('transitionend', onTransitionEnd);
      return () => track.removeEventListener('transitionend', onTransitionEnd);
    }, [normalizeSightSlider]);

    // 鼠标拖拽滑动（含触屏 pointer 事件）
    useEffect(() => {
      const track = trackRef.current;
      if (!track) return;

      const onPointerDown = (e: PointerEvent) => {
        if (e.button !== 0) return; // 仅左键
        const card = track.children[0] as HTMLElement;
        if (!card) return;
        // 阻止原生拖拽/文本选择抢占指针事件流
        e.preventDefault();
        try { track.setPointerCapture(e.pointerId); } catch { /* ignore */ }
        const gap = parseFloat(getComputedStyle(track).columnGap || '0');
        dragRef.current = {
          startX: e.clientX,
          startActive: activeSightRef.current,
          dragging: true,
          moved: false,
          cardW: card.offsetWidth,
          gap,
        };
        // 拖拽期间禁用过渡，实时跟随指针
        track.classList.add('is-jumping');
        track.classList.add('is-dragging');
      };

      const onPointerMove = (e: PointerEvent) => {
        const d = dragRef.current;
        if (!d.dragging) return;
        e.preventDefault();
        const dx = e.clientX - d.startX;
        if (Math.abs(dx) > 6) d.moved = true; // 拖拽距离阈值，区分点击
        const base = -(d.cardW + d.gap) * d.startActive;
        track.style.setProperty('--sights-shift', `${base + dx}px`);
      };

      const onPointerUp = (e: PointerEvent) => {
        const d = dragRef.current;
        if (!d.dragging) return;
        d.dragging = false;
        track.classList.remove('is-jumping');
        track.classList.remove('is-dragging');
        const dx = e.clientX - d.startX;
        const step = d.cardW + d.gap;
        if (step > 0 && Math.abs(dx) > 6) {
          // 拖过 1/3 卡宽即换卡（更灵敏，所有卡片都能拖到）
          const offset = dx / step;
          const dir = offset > 0 ? 1 : -1;
          const frac = Math.abs(offset) % 1;
          const whole = Math.floor(Math.abs(offset));
          let target = d.startActive - dir * whole;
          if (frac > 0.33) target -= dir; // 多拖一点多换一张
          setActive(target);
        } else {
          // 微小拖动 → 归位
          setActive(d.startActive);
        }
      };

      const onPointerCancel = () => {
        const d = dragRef.current;
        if (!d.dragging) return;
        d.dragging = false;
        track.classList.remove('is-jumping');
        track.classList.remove('is-dragging');
        setActive(d.startActive);
      };

      track.addEventListener('pointerdown', onPointerDown);
      track.addEventListener('pointermove', onPointerMove);
      track.addEventListener('pointerup', onPointerUp);
      track.addEventListener('pointercancel', onPointerCancel);
      // 拖出 track 后仍接收 move/up（pointer capture 保证）
      return () => {
        track.removeEventListener('pointerdown', onPointerDown);
        track.removeEventListener('pointermove', onPointerMove);
        track.removeEventListener('pointerup', onPointerUp);
        track.removeEventListener('pointercancel', onPointerCancel);
      };
      // 依赖 originalCount：初始 cards 为空时 track 尚未渲染，
      // 数据加载后重新绑定拖拽事件（否则永远绑不上）
    }, [setActive, originalCount]);

    const selectSightCard = (c: SightCard & { _sightIdx: number }) => {
      // 拖拽结束后的 click 不应触达卡片选择
      if (dragRef.current.moved) {
        dragRef.current.moved = false;
        return;
      }
      setActive(c._sightIdx);
      if (onSelect) onSelect(c);
    };

    if (originalCount === 0) return null;

    return (
      <div className="sights-track" ref={trackRef}>
        {cloneCards.map((c) => (
          <div
            key={`${c.id}-${c._sightIdx}`}
            className="sight-card"
            role="button"
            tabIndex={0}
            data-sight-index={c._sightIdx}
            onClick={() => selectSightCard(c)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectSightCard(c);
              }
            }}
          >
            <span className="sight-kicker">{c.kicker}</span>
            {c.pin && (
              <img className="sight-pin" src={c.pin} alt="" loading="lazy" draggable={false} />
            )}
            <h3>{c.title}</h3>
            <p>{c.desc}</p>
          </div>
        ))}
      </div>
    );
}
