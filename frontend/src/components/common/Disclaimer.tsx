import type { ReactNode } from 'react';

type DisclaimerType = 'warning' | 'info' | 'prototype';

interface DisclaimerProps {
  type?: DisclaimerType;
  message: string;
  children?: ReactNode;
}

const typeConfig: Record<DisclaimerType, { wrapper: string; icon: string; iconColor: string }> = {
  warning: {
    wrapper: 'bg-amber-50 border border-amber-300 text-amber-900',
    icon: '⚠',
    iconColor: 'text-amber-500',
  },
  info: {
    wrapper: 'bg-blue-50 border border-blue-200 text-blue-900',
    icon: 'ℹ',
    iconColor: 'text-blue-500',
  },
  prototype: {
    wrapper: 'bg-amber-50 border-2 border-red-400 text-amber-900',
    icon: '⚠',
    iconColor: 'text-red-500',
  },
};

export function Disclaimer({ type = 'warning', message, children }: DisclaimerProps) {
  const cfg = typeConfig[type];
  return (
    <div role="note" className={`rounded-lg p-4 ${cfg.wrapper}`}>
      <div className="flex items-start gap-2">
        <span aria-hidden="true" className={`mt-0.5 text-lg leading-none ${cfg.iconColor}`}>
          {cfg.icon}
        </span>
        <div className="text-sm font-medium leading-relaxed">
          <p>{message}</p>
          {children && <div className="mt-2">{children}</div>}
        </div>
      </div>
    </div>
  );
}
