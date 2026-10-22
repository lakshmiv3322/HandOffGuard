interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  label?: string;
}

const sizeMap = {
  sm: 'h-4 w-4 border-2',
  md: 'h-8 w-8 border-2',
  lg: 'h-12 w-12 border-4',
};

export function LoadingSpinner({ size = 'md', label = 'Loading…' }: LoadingSpinnerProps) {
  return (
    <div
      role="status"
      aria-label={label}
      className="flex flex-col items-center justify-center gap-3 py-12"
    >
      <div
        className={`${sizeMap[size]} animate-spin rounded-full border-slate-300 border-t-blue-600`}
      />
      <span className="text-sm text-slate-500">{label}</span>
    </div>
  );
}
