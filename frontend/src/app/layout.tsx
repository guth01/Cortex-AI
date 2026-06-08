import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: { default: 'Study Agent', template: '%s | Study Agent' },
  description: 'AI-powered personalized study companion — chat with your notes, generate flashcards, and build smart study plans.',
  keywords: ['study', 'AI', 'flashcards', 'study plan', 'notes'],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-[#0a0d14] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
