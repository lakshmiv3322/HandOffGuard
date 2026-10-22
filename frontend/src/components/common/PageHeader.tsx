import type { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  description?: string;
  actions?: ReactNode;
  breadcrumbs?: ReactNode;
}

export function PageHeader({ title, subtitle, description, actions, breadcrumbs }: PageHeaderProps) {
  const desc = description || subtitle;
  return (
    <div className="mb-6">
      {breadcrumbs && <div className="mb-2 text-sm text-slate-500">{breadcrumbs}</div>}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h1>
          {desc && <p className="mt-1 text-sm text-slate-500">{desc}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
    </div>
  );
}
