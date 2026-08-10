import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { AsyncState } from '../../../application/data/use-async';
import { AsyncView } from './AsyncView';

function state<T>(overrides: Partial<AsyncState<T>>): AsyncState<T> {
  return { data: null, error: null, loading: false, refetch: vi.fn(), ...overrides };
}

describe('AsyncView', () => {
  it('shows the loading state while loading, even if stale data or an error is also present', () => {
    render(
      <AsyncView state={state<string>({ loading: true, error: new Error('stale') })}>{(data) => <p>{data}</p>}</AsyncView>
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('shows the error state with a working retry wired to refetch', () => {
    const refetch = vi.fn();
    render(<AsyncView state={state<string>({ error: new Error('boom'), refetch })}>{(data) => <p>{data}</p>}</AsyncView>);
    expect(screen.getByRole('alert')).toBeInTheDocument();
    screen.getByRole('button', { name: 'Reintentar' }).click();
    expect(refetch).toHaveBeenCalledOnce();
  });

  it('treats null data as empty by default, for a detail view with no isEmpty callback', () => {
    render(<AsyncView state={state<string | null>({ data: null })}>{(data) => <p>{data}</p>}</AsyncView>);
    expect(screen.getByText('No hay nada que mostrar.')).toBeInTheDocument();
  });

  it('treats a non-null but empty list as empty when isEmpty says so', () => {
    render(
      <AsyncView state={state<string[]>({ data: [] })} isEmpty={(items) => items.length === 0} emptyText="Sin resultados.">
        {(items) => <p>{items.length} resultados</p>}
      </AsyncView>
    );
    expect(screen.getByText('Sin resultados.')).toBeInTheDocument();
  });

  it('renders the children with the data once loaded and non-empty', () => {
    render(
      <AsyncView state={state<string[]>({ data: ['a', 'b'] })} isEmpty={(items) => items.length === 0}>
        {(items) => <p>{items.length} resultados</p>}
      </AsyncView>
    );
    expect(screen.getByText('2 resultados')).toBeInTheDocument();
  });
});
