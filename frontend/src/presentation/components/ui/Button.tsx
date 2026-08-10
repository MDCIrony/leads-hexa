import type { ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'danger';

const VARIANT_CLASSES: Record<ButtonVariant, string> = {
  primary: 'bg-indigo-600 hover:bg-indigo-500 text-slate-100',
  secondary: 'border border-slate-800 text-slate-200 hover:bg-slate-800/50',
  danger: 'bg-rose-600 hover:bg-rose-500 text-slate-100',
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Shows an in-flight label and disables the button without the caller managing two props. */
  submitting?: boolean;
  submittingLabel?: string;
}

/** The only button in the app: six forms sharing this is what keeps focus and disabled states consistent. */
export function Button({
  variant = 'primary',
  submitting = false,
  submittingLabel = 'Enviando…',
  disabled,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled || submitting}
      className={`px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {submitting ? submittingLabel : children}
    </button>
  );
}
