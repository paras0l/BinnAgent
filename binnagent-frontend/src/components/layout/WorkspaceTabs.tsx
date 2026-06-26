import type { ReactNode } from 'react'

export interface WorkspaceTab<T extends string> {
  id: T
  label: string
  icon?: ReactNode
  description?: string
}

interface WorkspaceTabsProps<T extends string> {
  tabs: WorkspaceTab<T>[]
  activeTab: T
  onChange: (tab: T) => void
}

export function WorkspaceTabs<T extends string>({ tabs, activeTab, onChange }: WorkspaceTabsProps<T>) {
  return (
    <div className="overflow-x-auto rounded-[13px] border border-slate-200 bg-white p-1 shadow-[0_4px_14px_rgba(15,23,42,0.04)]">
      <div className="flex min-w-max gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`flex min-w-36 items-center gap-2 rounded-[10px] px-3 py-2 text-left text-sm transition-colors ${
              activeTab === tab.id
                ? 'bg-primary text-primary-foreground'
                : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
            }`}
          >
            {tab.icon}
            <span>
              <span className="block font-semibold">{tab.label}</span>
              {tab.description && <span className="block text-xs opacity-80">{tab.description}</span>}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
