import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], display: 'swap' });

export const metadata: Metadata = {
  title: { default: 'Study Agent', template: '%s | Study Agent' },
  description: 'AI-powered personalized study companion — chat with your notes, generate flashcards, and build smart study plans.',
  keywords: ['study', 'AI', 'flashcards', 'study plan', 'notes'],
};

import { ThemeProvider } from '@/components/ThemeProvider';
import { GoogleOAuthProvider } from '@react-oauth/google';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`min-h-screen bg-white dark:bg-[#0a0d14] text-slate-900 dark:text-slate-100 antialiased ${inter.className}`}>
        <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
          <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
            {children}
          </ThemeProvider>
        </GoogleOAuthProvider>
      </body>
    </html>
  );
}
