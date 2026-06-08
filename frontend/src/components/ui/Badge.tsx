const colors = {
  indigo: 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
  green: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
  yellow: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
  red: 'bg-red-500/15 text-red-400 border-red-500/30',
  blue: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  slate: 'bg-slate-500/15 text-slate-400 border-slate-500/30',
  purple: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
};

type Color = keyof typeof colors;

export default function Badge({
  children,
  color = 'indigo',
  className = '',
}: {
  children: React.ReactNode;
  color?: Color;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 text-xs font-medium rounded-full border ${colors[color]} ${className}`}
    >
      {children}
    </span>
  );
}
