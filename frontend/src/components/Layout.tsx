import { NavLink } from 'react-router-dom';
import {
  Upload, MessageSquare, Network, History,
  Settings, Shield, Sun, Moon, Brain,
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';

const NAV = [
  { to: '/',        icon: Upload,        label: 'Knowledge Ingest' },
  { to: '/chat',    icon: MessageSquare, label: 'AI Chat' },
  { to: '/wiki',    icon: Network,       label: 'Wiki & Graph' },
  { to: '/audit',   icon: History,       label: 'Audit Trail' },
  { to: '/settings',icon: Settings,      label: 'Settings' },
];

export default function Layout({ children }: { children: React.ReactNode }) {
  const { dark, toggle } = useTheme();

  return (
    <div className={`flex h-screen overflow-hidden ${dark ? 'dark' : ''}`}>
      {/* ── Sidebar ── */}
      <aside className="w-56 flex-shrink-0 flex flex-col bg-slate-50 dark:bg-slate-800 border-r border-slate-300 dark:border-slate-700">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-slate-300 dark:border-slate-700">
          <Brain className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
          <span className="font-bold text-slate-900 dark:text-white text-base tracking-tight">MarkMind</span>
          <span className="ml-auto text-[10px] text-slate-500 dark:text-slate-500 font-mono">Edge AI</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5 overflow-y-auto">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-200 dark:hover:bg-slate-700 hover:text-slate-900 dark:hover:text-slate-100'
                }`
              }
            >
              <Icon className="w-4 h-4 flex-shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-slate-300 dark:border-slate-700 space-y-2">
          {/* Offline Secure */}
          <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/50">
            <Shield className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
            <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">Offline Secure</span>
            <span className="w-1.5 h-1.5 bg-emerald-400 rounded-full animate-pulse ml-auto" />
          </div>

          {/* Theme toggle */}
          <button
            onClick={toggle}
            className="flex items-center gap-2 w-full px-2 py-1.5 rounded-lg text-xs text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors"
          >
            {dark ? <Sun className="w-3.5 h-3.5" /> : <Moon className="w-3.5 h-3.5" />}
            {dark ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
      </aside>

      {/* ── Main Content ── */}
      <main className="flex-1 overflow-hidden flex flex-col bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors">
        {children}
      </main>
    </div>
  );
}
