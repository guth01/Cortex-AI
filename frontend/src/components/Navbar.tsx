'use client';
import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import apiClient, { removeToken } from '@/lib/apiClient';
import type { User } from '@/types';

const navItems = [
  { href: '/dashboard', label: 'Dashboard', icon: '🏠' },
  { href: '/documents', label: 'Documents', icon: '📄' },
  { href: '/flashcards', label: 'Flashcards', icon: '🃏' },
  { href: '/history', label: 'History', icon: '📜' },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [isConnecting, setIsConnecting] = useState(false);
  const [user, setUser] = useState<User | null>(null);

  // Fetch user to check OAuth status
  useEffect(() => {
    const fetchUser = async () => {
      try {
        const { data } = await apiClient.get<User>('/auth/me');
        setUser(data);
      } catch {
        // ignore
      }
    };
    fetchUser();
  }, []);

  const handleLogout = () => {
    removeToken();
    router.push('/login');
  };

  const handleConnectCalendar = async () => {
    try {
      setIsConnecting(true);
      const res = await apiClient.post('/auth/google/url');
      if (res.data?.url) {
        window.location.href = res.data.url;
      }
    } catch (err) {
      console.error('Failed to get Google OAuth URL', err);
      alert('Failed to connect Google Calendar. Please try again.');
    } finally {
      setIsConnecting(false);
    }
  };

  return (
    <nav className="fixed top-0 left-0 right-0 z-40 glass border-b border-[#1f2d4a]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link href="/dashboard" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 via-purple-500 to-fuchsia-500 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20 group-hover:shadow-indigo-500/40 transition-all">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="font-bold text-slate-100 tracking-tight text-lg">Lumina</span>
          </Link>

          {/* Nav links */}
          <div className="flex items-center gap-1">
            {navItems.map(({ href, label, icon }) => {
              const active = pathname.startsWith(href);
              return (
                <Link
                  key={href}
                  href={href}
                  className={`
                    flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all
                    ${active
                      ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/30'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#1e2640]'
                    }
                  `}
                >
                  <span>{icon}</span>
                  <span className="hidden sm:block">{label}</span>
                </Link>
              );
            })}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            {user?.google_oauth_connected ? (
              <div className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="hidden sm:block">Calendar Connected</span>
              </div>
            ) : (
              <button
                onClick={handleConnectCalendar}
                disabled={isConnecting}
                className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-slate-200 bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 hover:border-indigo-500/50 transition-all disabled:opacity-50"
              >
                <svg className="w-4 h-4 text-indigo-400" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19 4h-1V2h-2v2H8V2H6v2H5c-1.11 0-1.99.9-1.99 2L3 20a2 2 0 002 2h14c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 16H5V10h14v10zM9 14H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2zm-8 4H7v-2h2v2zm4 0h-2v-2h2v2zm4 0h-2v-2h2v2z" />
                </svg>
                <span className="hidden sm:block">{isConnecting ? 'Connecting...' : 'Connect Calendar'}</span>
              </button>
            )}

            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-slate-400 hover:text-red-400 hover:bg-red-500/10 transition-all"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              <span className="hidden sm:block">Logout</span>
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
