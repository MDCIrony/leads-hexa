import axios, { AxiosHeaders } from 'axios';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ErrorState } from './ErrorState';

function axiosError(status: number, data: unknown) {
  return new axios.AxiosError('Request failed', String(status), undefined, undefined, {
    status,
    statusText: '',
    headers: new AxiosHeaders(),
    config: { headers: new AxiosHeaders() },
    data,
  });
}

describe('ErrorState', () => {
  it('reads its message from the api-error translator, not a hardcoded string', () => {
    render(<ErrorState error={axiosError(403, { error_code: 'forbidden', message: 'Sin permiso para ver esto.' })} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Sin permiso para ver esto.');
  });

  it('falls back to a generic message for a plain, non-API error', () => {
    render(<ErrorState error={new Error('network down')} />);
    expect(screen.getByRole('alert')).toHaveTextContent('Ha ocurrido un error inesperado.');
  });

  it('omits the retry button when no handler is given', () => {
    render(<ErrorState error={new Error('boom')} />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('calls the retry handler when its button is clicked', async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new Error('boom')} onRetry={onRetry} />);

    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(onRetry).toHaveBeenCalledOnce();
  });
});
