import { cloneElement, isValidElement, useId, type ReactElement } from 'react';

interface FieldProps {
  label: string;
  error?: string;
  /** A single Input (or compatible control) — Field wires its id/aria attributes, the caller never has to. */
  children: ReactElement<{ id?: string; 'aria-describedby'?: string; hasError?: boolean }>;
}

/** Label associated to its control by id: the one thing that makes a form accessible without every page repeating it. */
export function Field({ label, error, children }: FieldProps) {
  const controlId = useId();
  const errorId = `${controlId}-error`;

  const control = isValidElement(children)
    ? cloneElement(children, {
        id: controlId,
        'aria-describedby': error ? errorId : undefined,
        hasError: Boolean(error),
      })
    : children;

  return (
    <div className="space-y-1">
      <label htmlFor={controlId} className="block text-sm font-medium text-slate-200">
        {label}
      </label>
      {control}
      {/* The slot always reserves one line: showing an error must not push the form down. */}
      {error ? (
        <p id={errorId} role="alert" className="text-sm text-rose-400 min-h-5">
          {error}
        </p>
      ) : (
        <p aria-hidden="true" className="text-sm min-h-5">
          {'\u00A0'}
        </p>
      )}
    </div>
  );
}
