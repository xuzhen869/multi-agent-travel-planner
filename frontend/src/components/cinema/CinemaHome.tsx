'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { Compass, ArrowRight } from 'lucide-react';
import { SightSlider, type SightCard } from './SightSlider';
import { AgentPipeline } from './AgentPipeline';
import type { TripListItem } from '@/types';

/* ============================================================
   动画工具函数（模板原数学）
   ============================================================ */
const clamp = (v: number, min = 0, max = 1) => Math.min(max, Math.max(min, v));
const smoothstep = (e0: number, e1: number, v: number) => {
  const x = clamp((v - e0) / (e1 - e0));
  return x * x * (3 - 2 * x);
};
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const segmentInOut = (s: number, a: number, b: number, c: number, d: number) => {
  const enter = smoothstep(a, b, s);
  const exit = smoothstep(c, d, s);
  return { enter, exit, active: enter * (1 - exit) };
};

/* ============================================================
   主舞台（规范 DOM 结构）
   ============================================================ */
export function CinemaHome() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const stageRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLElement>(null);
  const [activeSightCards, setActiveSightCards] = useState<SightCard[]>([]);
  const [agentActive, setAgentActive] = useState(false);
  const [recentTripId, setRecentTripId] = useState<string | null>(null);
  // 右上角 GIF：仅首屏显示，翻过第 1 幕后本会话内永久隐藏，刷新后重新显示
  const [gifVisible, setGifVisible] = useState(true);
  const gifHiddenRef = useRef(false);

  // —— 状态（ref 供动画循环读）——
  const targetMouseX = useRef(0);
  const targetMouseY = useRef(0);
  const mouseX = useRef(0);
  const mouseY = useRef(0);
  const targetScroll = useRef(0);
  const smoothScroll = useRef(0);
  const initialized = useRef(false);
  const rafPending = useRef(false);
  const reduceMotion = useRef<MediaQueryList | null>(null);

  /* ============================================================
     数据接入：行程滑轨 + 最近行程（SSE）
     ============================================================ */
  const loadTrips = useCallback(async () => {
    if (!user) return;
    try {
      const trips = await api.listTrips(0, 50);
      const active = trips.find((t) => t.status === 'recommending' || t.status === 'planning');
      if (active) setRecentTripId(active.id);

      const cards: SightCard[] = trips.slice(0, 8).map((t: TripListItem, i: number) => ({
        id: t.id,
        kicker: t.mode === 'direct' ? '直接定制' : 'AI 推荐',
        title: t.title?.split('（')[0] || t.destination || '未命名行程',
        desc: `${t.destination || ''} · ${formatMoney(t.budget_total, t.budget_currency)}`,
        pin: PIN_ICONS[i % PIN_ICONS.length],
        href: `/trips/${t.id}`,
      }));
      setActiveSightCards(cards);
    } catch {
      /* 未登录或读取失败 → 保持演示卡片 */
    }
  }, [user]);

  const loadDemoCards = useCallback(async () => {
    const demos: SightCard[] = [
      { id: 'demo-1', kicker: '热门目的地', title: '东京', desc: '美食·都市·文化，AI 为你搭配合拍行程', pin: '/icons/icon1.png' },
      { id: 'demo-2', kicker: '深度人文', title: '京都', desc: '老城与庙宇，松弛节奏首选', pin: '/icons/icon2.png' },
      { id: 'demo-3', kicker: '海岛度假', title: '巴厘岛', desc: '沙滩·梯田·SPA，预算弹性最大', pin: '/icons/icon3.png' },
      { id: 'demo-4', kicker: '冒险体验', title: '冰岛', desc: '极光与冰川，紧凑打卡之旅', pin: '/icons/icon1.png' },
    ];
    setActiveSightCards(demos);
  }, []);

  useEffect(() => {
    if (loading) return;
    if (user) loadTrips();
    else loadDemoCards();
  }, [user, loading, loadTrips, loadDemoCards]);

  /* ============================================================
     动画引擎（模板 update() 原数学）
     ============================================================ */
  const update = useCallback(() => {
    const stage = stageRef.current;
    const scrollEl = scrollRef.current;
    if (!stage || !scrollEl) return;
    const rm = reduceMotion.current;
    const rmMatches = rm?.matches ?? false;

    // 滚动距离（基于外层容器位移）
    const dist = clamp(-scrollEl.getBoundingClientRect().top, 0, scrollEl.offsetHeight - window.innerHeight);
    targetScroll.current = dist;
    if (!initialized.current || rmMatches) {
      smoothScroll.current = targetScroll.current;
      initialized.current = true;
    } else {
      smoothScroll.current = lerp(smoothScroll.current, targetScroll.current, 0.14);
    }
    if (Math.abs(smoothScroll.current - targetScroll.current) < 0.08) {
      smoothScroll.current = targetScroll.current;
    }

    // 鼠标平滑
    mouseX.current = lerp(mouseX.current, targetMouseX.current, 0.12);
    mouseY.current = lerp(mouseY.current, targetMouseY.current, 0.12);
    const mx = rmMatches ? 0 : mouseX.current;
    const my = rmMatches ? 0 : mouseY.current;

    const sc = smoothScroll.current;
    // 右上角 GIF：一旦翻过第 1 幕（650px）即永久隐藏（本次会话内）
    if (sc > 650 && !gifHiddenRef.current) {
      gifHiddenRef.current = true;
      setGifVisible(false);
    }
    const frame2 = segmentInOut(sc, 560, 900, 1300, 1620);
    const frame3 = segmentInOut(sc, 1760, 2140, 2540, 2700);
    const progress = clamp(sc / 2700);
    const introExit = smoothstep(90, 650, sc);
    const sightsEnterRaw = smoothstep(2760, 3560, sc);
    const sightsEnter = Math.pow(sightsEnterRaw, 1.55);
    const sightsControlsEnter = smoothstep(3360, 3660, sc);
    const blurActive = clamp(frame2.active + frame3.active);
    const frame2Opacity = frame2.active * (1 - frame3.enter);
    const splitDrift = Math.pow(frame2.enter, 1.5);
    const panel2Opacity = frame2.active * (1 - frame2.exit);
    const panel3Opacity = frame3.active * (1 - frame3.exit);
    const backScale = 0.76 + progress * 0.2 + frame2.enter * 0.18 + frame3.enter * 0.16;
    const sharedHeroY = progress * -74;
    const sharedHeroScale = progress * 0.23;
    const sightsScreenTop = Math.min(220, Math.max(112, window.innerHeight * 0.19)) - 50;
    const sightsParentTop = window.innerHeight - (window.innerHeight - sightsScreenTop) / backScale;

    // 第 4 幕滚动激活（进入时激活，离开时取消，避免返回顶部仍显示）
    const agentEnter = smoothstep(3660, 4200, sc);
    setAgentActive(agentEnter > 0.02);

    const el = stage;
    const set = (k: string, v: string) => el.style.setProperty(k, v);

    set('--mx', mx.toFixed(4));
    set('--my', my.toFixed(4));

    set('--back-opacity', `${(1 - frame2.active * 0.06).toFixed(4)}`);
    set('--back-x', `${(mx * -12).toFixed(4)}px`);
    set('--back-y', `${(my * -4).toFixed(4)}px`);
    set('--back-scale', `${backScale.toFixed(4)}`);
    set('--four-y', `${(10 + progress * 10).toFixed(4)}vh`);
    set('--four-scale', `${(0.78 + progress * 0.16).toFixed(4)}`);
    set('--bazaar-y', `${(20 - progress * 8).toFixed(4)}vh`);
    set('--blur-px', `${(blurActive * 14).toFixed(4)}px`);
    set('--back-brightness', `${(1 - blurActive * 0.255).toFixed(4)}`);
    set('--bazaar-blur-px', `${(frame2.active * 14).toFixed(4)}px`);
    set('--bazaar-brightness', `${(1 - frame2.active * 0.255 - frame3.active * 0.06).toFixed(4)}`);
    set('--bazaar-saturation', `${(1 + frame3.active * 0.18).toFixed(4)}`);
    set('--shade-opacity', '1');
    set('--shade-z', frame2.active > 0.02 ? '2' : '0');
    set('--shade-top-alpha', `${(blurActive * 0.465).toFixed(4)}`);
    set('--shade-mid-alpha', `${(blurActive * 0.42).toFixed(4)}`);
    set('--shade-bottom-alpha', `${(blurActive * 0.51).toFixed(4)}`);

    set('--title-y', `${(introExit * -210).toFixed(4)}px`);
    set('--title-scale', `${(1 - introExit * 0.08).toFixed(4)}`);
    set('--title-opacity', `${(1 - introExit).toFixed(4)}`);

    set('--bridge-x', `calc(-50% + ${(mx * 18).toFixed(4)}px)`);
    set('--bridge-y', `${(my * 8 + sharedHeroY - frame2.exit * 760).toFixed(4)}px`);
    set('--bridge-bottom', `${(5 - frame2.enter * 13).toFixed(4)}vh`);
    set('--bridge-width', `${(67.2 + frame2.enter * 37.8).toFixed(4)}vw`);
    set('--bridge-scale', `${(1.02 + sharedHeroScale + frame2.exit * 0.46).toFixed(4)}`);

    set('--split-left-x', `calc(-50% + ${(-splitDrift * 46).toFixed(4)}vw + ${(mx * 22).toFixed(4)}px)`);
    set('--split-left-y', `${(my * 10 + sharedHeroY - splitDrift * 180).toFixed(4)}px`);
    set('--split-left-scale', `${(1 + sharedHeroScale + frame2.enter * 0.74).toFixed(4)}`);
    set('--split-right-x', `calc(-50% + ${(splitDrift * 46).toFixed(4)}vw + ${(mx * 22).toFixed(4)}px)`);
    set('--split-right-y', `${(my * 10 + sharedHeroY - splitDrift * 180).toFixed(4)}px`);
    set('--split-right-scale', `${(1 + sharedHeroScale + frame2.enter * 0.74).toFixed(4)}`);

    set('--frame2-opacity', `${frame2Opacity.toFixed(4)}`);
    set('--frame2-x', `calc(-50% + ${(mx * 10).toFixed(4)}px)`);
    set('--frame2-y', `calc(-50% + ${(my * 8 - frame2.exit * 150).toFixed(4)}px)`);
    set('--frame2-scale', `${(1.06 + frame2.enter * 0.08 + frame2.exit * 0.08).toFixed(4)}`);

    set('--intro-copy-y', `${(introExit * 90).toFixed(4)}px`);
    set('--intro-copy-opacity', `${(1 - introExit).toFixed(4)}`);
    set('--panel2-opacity', `${panel2Opacity.toFixed(4)}`);
    set('--panel2-y', `calc(-50% + ${(-frame2.exit * 86 + (1 - frame2.enter) * 58).toFixed(4)}px)`);
    set('--panel3-opacity', `${panel3Opacity.toFixed(4)}`);
    set('--panel3-y', `calc(-50% + ${(-frame3.exit * 86 + (1 - frame3.enter) * 58).toFixed(4)}px)`);

    set('--sights-opacity', `${sightsEnter.toFixed(4)}`);
    set('--sights-controls-opacity', `${sightsControlsEnter.toFixed(4)}`);
    set('--sights-visibility', sightsEnter > 0.01 ? 'visible' : 'hidden');
    set('--sights-y', '0px');
    set('--sights-enter-x', `${((1 - sightsEnter) * 420).toFixed(4)}vw`);
    set('--sights-scale', `${(1 / backScale).toFixed(4)}`);
    set('--sights-top', `${sightsParentTop.toFixed(4)}px`);
    set('--sights-screen-top', `${sightsScreenTop.toFixed(4)}px`);
  }, []);

  const requestTick = useCallback(() => {
    if (rafPending.current) return;
    rafPending.current = true;
    requestAnimationFrame(() => {
      rafPending.current = false;
      update();
      const stillNeeds =
        Math.abs(smoothScroll.current - targetScroll.current) > 0.08 ||
        Math.abs(mouseX.current - targetMouseX.current) > 0.001 ||
        Math.abs(mouseY.current - targetMouseY.current) > 0.001;
      if (stillNeeds) requestTick();
    });
  }, [update]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;
    reduceMotion.current = window.matchMedia('(prefers-reduced-motion: reduce)');

    const onScroll = () => requestTick();
    const onResize = () => requestTick();
    const onPointer = (e: PointerEvent) => {
      targetMouseX.current = e.clientX / window.innerWidth - 0.5;
      targetMouseY.current = e.clientY / window.innerHeight - 0.5;
      requestTick();
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onResize);
    window.addEventListener('pointermove', onPointer, { passive: true });
    requestTick();

    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('pointermove', onPointer);
    };
  }, [requestTick]);

  const goto = (path: string) => router.push(path);
  const isLoggedIn = !!user;

  return (
    <main className="site-shell">
      <section className="cinema-scroll" ref={scrollRef} id="cinema" aria-label="旅行计划助手滚动叙事">
        <div className="stage" ref={stageRef}>
          <div className="world">
            {/* ===== 天空 ===== */}
            <img className="scene-img sky-img" src="/images/01-sky.png" alt="" />

            {/* ===== 顶部导航 ===== */}
            <header className="site-header" aria-label="主导航">
              <a className="site-logo" href="#cinema">
                <Compass size={22} />
                <span>旅行计划助手</span>
              </a>
              <nav className="site-nav" aria-label="主菜单">
                <a href="#cinema">简介</a>
                <a href="#bridge">画像</a>
                <a href="#bazaar">方案</a>
                <a href="#routes">行程</a>
              </nav>
              <button className="language-switcher" aria-label="切换语言">
                {gifVisible && <img className="lang-gif" src="/images/icons8-shuangjiang-white-tall.gif" alt="" aria-hidden="true" />}
                <span>中</span>
                <span aria-hidden="true">⌄</span>
              </button>
            </header>

            {/* ===== 背景容器（back-four / 滑轨 / back-bazaar 子层） ===== */}
            <div className="back-stack">
              <img className="scene-img back-img back-four" src="/images/02-back-four-glow.png" alt="" />
              <section className="sights-slider" aria-label="行程滑轨">
                <SightSlider cards={activeSightCards} onSelect={(c) => {
                  if (c.href) goto(c.href);
                  else if (!isLoggedIn) goto('/register');
                }} />
              </section>
              <img className="scene-img back-img back-bazaar" src="/images/03-back-bazaar.png" alt="" />
            </div>

            {/* ===== Hero 标题 ===== */}
            <h1 className="hero-title">TRIPLOT</h1>

            {/* ===== 分裂画面（左右单图） ===== */}
            <img className="scene-img splitframe-img splitframe-left" src="/images/04-splitframe-left.png" alt="" />
            <img className="scene-img splitframe-img splitframe-right" src="/images/05-splitframe-right.png" alt="" />

            {/* ===== 桥 ===== */}
            <img className="scene-img bridge-img" src="/images/06-bridge.png" alt="" />

            {/* ===== 河流特写 ===== */}
            <img className="scene-img frame-two-img" src="/images/07-frame-two-river.png" alt="" />

            {/* ===== 蓝色遮罩 ===== */}
            <div className="shade" />
          </div>

          {/* ===== 简介 + 标签 + CTA ===== */}
          <section className="intro-copy" aria-label="产品简介">
            <p>AI Multi-Agent 驱动，从画像到路线一步到位</p>
            <div className="hero-tags" aria-label="核心亮点">
              <span>AI 画像分析</span>
              <span>多方案推荐</span>
              <span>实时进度</span>
            </div>
            <div className="hero-cta-row">
              {loading ? null : isLoggedIn ? (
                <>
                  <button className="hero-cta" onClick={() => goto('/planner')}>
                    开始规划新行程 <ArrowRight size={18} />
                  </button>
                  <button className="hero-cta-secondary" onClick={() => goto('/trips')}>
                    查看历史行程
                  </button>
                </>
              ) : (
                <>
                  <button className="hero-cta" onClick={() => goto('/register')}>
                    免费开始使用 <ArrowRight size={18} />
                  </button>
                  <button className="hero-cta-secondary" onClick={() => goto('/login')}>
                    已有账号？登录
                  </button>
                </>
              )}
            </div>
          </section>

          {/* ===== 第 1 幕故事面板：画像 ===== */}
          <section className="story-panel story-panel-bridge" aria-label="画像详情">
            <h2>从一张画像开始</h2>
            <p>填一次偏好，AI 读懂你的旅行人格</p>
            <dl className="facts">
              <div>
                <dt>≤12字</dt>
                <dd>专属人格标签</dd>
              </div>
              <div>
                <dt>3-5个</dt>
                <dd>核心特征关键词</dd>
              </div>
            </dl>
            <button className="note-button" onClick={() => goto(isLoggedIn ? '/planner' : '/register')}>
              <span aria-hidden="true">↗</span>
              <span>填写偏好</span>
            </button>
          </section>

          {/* ===== 第 2 幕故事面板：方案 ===== */}
          <section className="story-panel story-panel-bazaar" aria-label="方案详情">
            <h2>两到三套方案，一个合拍的你</h2>
            <p>差异化方案，每条 ≤10 字推荐理由</p>
            <dl className="facts">
              <div>
                <dt>2-3套</dt>
                <dd>差异化行程方案</dd>
              </div>
              <div>
                <dt>10字</dt>
                <dd>每方案推荐理由</dd>
              </div>
            </dl>
            <button className="note-button" onClick={() => goto(isLoggedIn ? '/trips' : '/register')}>
              <span aria-hidden="true">↗</span>
              <span>查看推荐方案</span>
            </button>
          </section>

          {/* ===== 第 4 幕：Agent 流水线 ===== */}
          <AgentPipeline tripId={recentTripId || undefined} active={agentActive} />

          {/* ===== 滚动指示 ===== */}
          <div className="scroll-cue">SCROLL</div>
        </div>
      </section>
    </main>
  );
}

/* 滑轨卡片 pin 图标池 */
const PIN_ICONS = [
  '/icons/icon1.png',
  '/icons/icon2.png',
  '/icons/icon3.png',
];

function formatMoney(amount: number | null | undefined, currency: string | null | undefined = 'CNY'): string {
  if (amount == null) return '预算待定';
  const c = currency || 'CNY';
  const symbols: Record<string, string> = { CNY: '¥', USD: '$', JPY: '¥', EUR: '€', KRW: '₩', THB: '฿' };
  return `${symbols[c] || c}${amount.toLocaleString()}`;
}
