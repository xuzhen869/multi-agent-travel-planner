'use client';

import Link from 'next/link';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { Compass, Menu, X } from 'lucide-react';
import { useState } from 'react';

export function Header() {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const isAuthPage = pathname === '/login' || pathname === '/register';
  // 首页使用电影感内嵌导航（cinema-header），隐藏全局 Header
  const isHome = pathname === '/';
  if (isAuthPage || isHome) return null;

  return (
    <header className="sticky top-0 z-40 border-b border-gray-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 text-xl font-bold text-indigo-600">
          <Compass className="h-6 w-6" />
          <span>旅行规划助手</span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6 text-sm font-medium">
          {!loading && user ? (
            <>
              <Link href="/trips" className="text-gray-600 hover:text-indigo-600 transition-colors">我的行程</Link>
              <Link href="/planner" className="text-gray-600 hover:text-indigo-600 transition-colors">新建行程</Link>
              <Link href="/settings" className="text-gray-600 hover:text-indigo-600 transition-colors">偏好设置</Link>
              <button onClick={async () => { await logout(); router.push('/'); }} className="text-gray-400 hover:text-red-500 transition-colors">登出</button>
            </>
          ) : !loading ? (
            <>
              <Link href="/login" className="text-gray-600 hover:text-indigo-600 transition-colors">登录</Link>
              <Link href="/register" className="rounded-full bg-indigo-600 px-4 py-1.5 text-white hover:bg-indigo-700 transition-colors">注册</Link>
            </>
          ) : null}
        </nav>

        {/* Mobile hamburger */}
        <button onClick={() => setOpen(!open)} className="md:hidden rounded-lg p-2 hover:bg-gray-100">
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden border-t border-gray-100 bg-white px-4 py-4 space-y-3">
          {user ? (
            <>
              <Link href="/trips" onClick={() => setOpen(false)} className="block text-gray-700 py-1">我的行程</Link>
              <Link href="/planner" onClick={() => setOpen(false)} className="block text-gray-700 py-1">新建行程</Link>
              <Link href="/settings" onClick={() => setOpen(false)} className="block text-gray-700 py-1">偏好设置</Link>
              <button onClick={async () => { await logout(); router.push('/'); setOpen(false); }} className="block text-red-500 py-1">登出</button>
            </>
          ) : (
            <>
              <Link href="/login" onClick={() => setOpen(false)} className="block text-gray-700 py-1">登录</Link>
              <Link href="/register" onClick={() => setOpen(false)} className="block text-indigo-600 py-1 font-medium">注册</Link>
            </>
          )}
        </div>
      )}
    </header>
  );
}
