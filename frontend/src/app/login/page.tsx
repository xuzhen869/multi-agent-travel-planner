'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/lib/auth-context';
import { api } from '@/lib/api';
import { LogIn, Loader2 } from 'lucide-react';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [oauthBusy, setOauthBusy] = useState<'google' | 'github' | null>(null);
  const { login } = useAuth();
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
      router.push('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '登录失败');
    } finally {
      setSubmitting(false);
    }
  };

  // OAuth：获取授权链接并跳转（GET /api/auth/oauth/{provider}/url）
  const handleOAuth = async (provider: 'google' | 'github') => {
    setError('');
    setOauthBusy(provider);
    try {
      const res = provider === 'google' ? await api.getGoogleAuthUrl() : await api.getGithubAuthUrl();
      if (!res.url) {
        setError(res.error || `${provider === 'google' ? 'Google' : 'GitHub'} 登录未配置`);
        return;
      }
      window.location.href = res.url;
    } catch {
      setError('无法获取授权链接');
    } finally {
      setOauthBusy(null);
    }
  };

  return (
    <div className="flex min-h-[80vh] items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <LogIn className="mx-auto h-10 w-10 text-indigo-600" />
          <h1 className="mt-4 text-2xl font-bold text-gray-900">欢迎回来</h1>
          <p className="mt-1 text-sm text-gray-500">登录你的旅行规划助手账号</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600">{error}</div>}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">邮箱</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="your@email.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">密码</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8}
              className="w-full rounded-lg border border-gray-300 px-4 py-2.5 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
              placeholder="至少 8 位" />
          </div>
          <button type="submit" disabled={submitting}
            className="w-full rounded-lg bg-indigo-600 py-2.5 text-white font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors">
            {submitting ? '登录中...' : '登录'}
          </button>
        </form>

        {/* OAuth 分隔 */}
        <div className="my-5 flex items-center gap-3 text-xs text-gray-400">
          <div className="h-px flex-1 bg-gray-200" /> 或 <div className="h-px flex-1 bg-gray-200" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <button onClick={() => handleOAuth('google')} disabled={oauthBusy !== null}
            className="flex items-center justify-center gap-2 rounded-lg border border-gray-300 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors">
            {oauthBusy === 'google' ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <svg viewBox="0 0 24 24" className="h-4 w-4"><path fill="#4285F4" d="M23.5 12.3c0-.9-.1-1.5-.3-2.2H12v4.1h6.5c-.1 1-.8 2.6-2.3 3.7l3.5 2.7c2.1-2 3.8-4.9 3.8-8.3z"/><path fill="#34A853" d="M12 24c3.2 0 5.9-1.1 7.9-2.9l-3.5-2.7c-1 .7-2.3 1.2-4.4 1.2-3.4 0-6.3-2.3-7.3-5.3L1.1 17c2 4 6.1 7 10.9 7z"/><path fill="#FBBC05" d="M4.7 14.3c-.2-.7-.4-1.5-.4-2.3s.2-1.6.4-2.3L1.1 7C.4 8.4 0 10.1 0 12s.4 3.6 1.1 5l3.6-2.7z"/><path fill="#EA4335" d="M12 4.7c2.4 0 4 1 4.9 1.9L20.3 3C17.9.9 15.2 0 12 0 5.1 0 1.1 3 1.1 7l3.6 2.7c1-3 3.9-5.3 7.3-5.3z"/></svg>
            )}
            Google
          </button>
          <button onClick={() => handleOAuth('github')} disabled={oauthBusy !== null}
            className="flex items-center justify-center gap-2 rounded-lg border border-gray-300 py-2.5 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors">
            {oauthBusy === 'github' ? <Loader2 className="h-4 w-4 animate-spin" /> : (
              <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current"><path d="M12 0C5.4 0 0 5.4 0 12c0 5.3 3.4 9.8 8.2 11.4.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.5-1.4-1.3-1.7-1.3-1.7-1.1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1.1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2-.1-.3-.5-1.5.1-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17.3 4.4 18.3 4.7 18.3 4.7c.6 1.7.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.4.4.8 1.1.8 2.2v3.3c0 .3.2.7.8.6A12 12 0 0 0 24 12c0-6.6-5.4-12-12-12z"/></svg>
            )}
            GitHub
          </button>
        </div>

        <p className="mt-6 text-center text-sm text-gray-500">
          还没有账号？<Link href="/register" className="text-indigo-600 hover:underline">注册</Link>
        </p>
      </div>
    </div>
  );
}
