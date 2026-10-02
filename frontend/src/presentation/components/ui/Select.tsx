import { forwardRef, type SelectHTMLAttributes } from 'react';

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  hasError?: boolean;
}

/** Input's twin for a native <select>: same border, focus ring and error state. */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { hasError = false, className = '', ...rest },
  ref
) {
  const borderColor = hasError ? 'border-rose-500/50' : 'border-slate-800';
  return (
    <select
      ref={ref}
      className={`w-full px-3 py-2 rounded-lg bg-slate-950 border ${borderColor} text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 ${className}`}
      {...rest}
    />
  );
});
