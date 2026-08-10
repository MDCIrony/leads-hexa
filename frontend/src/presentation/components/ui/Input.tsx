import { forwardRef, type InputHTMLAttributes } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  hasError?: boolean;
}

// forwardRef so Field can wire <label htmlFor> straight to the DOM input.
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { hasError = false, className = '', ...rest },
  ref
) {
  const borderColor = hasError ? 'border-rose-500/50' : 'border-slate-800';
  return (
    <input
      ref={ref}
      className={`w-full px-3 py-2 rounded-lg bg-slate-950 border ${borderColor} text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 ${className}`}
      {...rest}
    />
  );
});
