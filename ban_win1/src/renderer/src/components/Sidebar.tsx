import React from 'react'
import {
  Layers,
  Download,
  BookOpen,
  Sparkles,
  Settings,
  ShieldCheck
} from 'lucide-react'

export type NavTab = 'quan_ly' | 'tai_reels' | 'cao_truyen' | 'gemini' | 'cai_dat' | 'ban_quyen'

interface SidebarProps {
  currentTab: NavTab
  onSelectTab: (tab: NavTab) => void
  totalVideos?: number
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, totalVideos = 0 }) => {
  const navItems = [
    { id: 'quan_ly' as NavTab, label: 'Quản lý', icon: Layers, badge: totalVideos },
    { id: 'tai_reels' as NavTab, label: 'Tải Reels', icon: Download },
    { id: 'cao_truyen' as NavTab, label: 'Cào Truyện', icon: BookOpen },
    { id: 'gemini' as NavTab, label: 'Gemini AI', icon: Sparkles, highlight: true },
    { id: 'cai_dat' as NavTab, label: 'Cài đặt', icon: Settings },
    { id: 'ban_quyen' as NavTab, label: 'Bản quyền', icon: ShieldCheck }
  ]

  return (
    <aside className="w-64 bg-white/95 border-r border-slate-200/80 flex flex-col justify-between select-none shadow-[1px_0_10px_rgba(0,0,0,0.02)]">
      <div>
        {/* App Branding */}
        <div className="p-5 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-purple-500 flex items-center justify-center shadow-md shadow-indigo-500/20">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-base tracking-wide text-slate-800">
                Ban Win 1.0
              </h1>
              <p className="text-[11px] text-slate-400 font-medium">Automation Suite</p>
            </div>
          </div>
          <span className="text-[10px] px-2 py-0.5 rounded-full font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200">
            PRO
          </span>
        </div>

        {/* Navigation list */}
        <nav className="p-3 space-y-1 mt-2">
          {navItems.map((item) => {
            const Icon = item.icon
            const isActive = currentTab === item.id
            return (
              <button
                key={item.id}
                onClick={() => onSelectTab(item.id)}
                className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all duration-150 ${isActive
                    ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md shadow-indigo-600/25'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80'
                  }`}
              >
                <div className="flex items-center gap-3">
                  <Icon
                    className={`w-4 h-4 transition-transform duration-150 ${isActive ? 'text-white scale-110' : item.highlight ? 'text-purple-600' : 'text-slate-400'
                      }`}
                  />
                  <span>{item.label}</span>
                </div>
                {item.badge !== undefined && item.badge > 0 && (
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-semibold ${isActive ? 'bg-white/20 text-white' : 'bg-slate-100 text-slate-600 border border-slate-200/60'
                      }`}
                  >
                    {item.badge}
                  </span>
                )}
                {item.highlight && !isActive && (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-purple-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-purple-500"></span>
                  </span>
                )}
              </button>
            )
          })}
        </nav>
      </div>

      {/* Footer Info */}
      <div className="p-4 border-t border-slate-100">
        <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80 flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-700">Hệ thống</p>
            <p className="text-[11px] text-slate-400">Local SQLite • Fluent Design</p>
          </div>
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-sm shadow-emerald-500/50" />
        </div>
      </div>
    </aside>
  )
}
