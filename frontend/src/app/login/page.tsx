'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import apiClient, { setToken } from '@/lib/apiClient';
import Button from '@/components/ui/Button';

export default function LoginPage() {
  const router = useRouter();
  const [form, setForm] = useState({ email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [errorKey, setErrorKey] = useState(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const { data } = await apiClient.post('/auth/login', form);
      setError('');
      setToken(data.access_token);
      router.push('/dashboard');
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Invalid email or password');
      setErrorKey((prev) => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-white dark:bg-[#0a0d14]">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[600px] h-[400px] bg-indigo-600/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 mb-4 shadow-xl shadow-indigo-500/30">
            <span className="text-2xl">🧠</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Welcome back</h1>
          <p className="text-slate-500 mt-1 text-sm">Sign in to your study dashboard</p>
        </div>

        {/* Card */}
        <div className="glass rounded-2xl p-8 shadow-2xl">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-700 dark:text-slate-300 mb-2">Email</label>
              <input
                type="email"
                required
                value={form.email}
                onChange={(e) => { setForm({ ...form, email: e.target.value }); setError(''); }}
                placeholder="you@example.com"
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a] text-slate-900 dark:text-slate-100 placeholder-slate-600 text-sm transition-all focus:ring-2 focus:ring-indigo-500/50 outline-none"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 dark:text-slate-700 dark:text-slate-300 mb-2">Password</label>
              <input
                type="password"
                required
                value={form.password}
                onChange={(e) => { setForm({ ...form, password: e.target.value }); setError(''); }}
                placeholder="••••••••"
                className="w-full px-4 py-3 rounded-xl bg-slate-50 dark:bg-[#0f1623] border border-slate-200 dark:border-[#1f2d4a] text-slate-900 dark:text-slate-100 placeholder-slate-600 text-sm transition-all focus:ring-2 focus:ring-indigo-500/50 outline-none"
              />
            </div>

            <div className="min-h-[3rem]">
              {error && (
                <div key={errorKey} className="animate-shake text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-xl px-4 py-3">
                  {error}
                </div>
              )}
            </div>

            <Button type="submit" loading={loading} size="lg" className="w-full">
              Sign In
            </Button>
          </form>

          <p className="text-center text-sm text-slate-500 mt-6">
            Don&apos;t have an account?{' '}
            <Link href="/register" className="text-indigo-400 hover:text-indigo-300 font-medium transition-colors">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
