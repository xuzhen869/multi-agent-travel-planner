import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/lib/auth-context';
import { Header } from '@/components/layout/Header';

export const metadata: Metadata = {
  title: '旅行规划助手 — AI 驱动的智能旅行规划',
  description: 'Multi-Agent 协作，为用户画像推荐个性化旅行方案',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-gray-50">
        <AuthProvider>
          <Header />
          <main className="flex-1">{children}</main>
        </AuthProvider>
      </body>
    </html>
  );
}
