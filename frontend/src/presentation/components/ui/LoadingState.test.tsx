import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { LoadingState } from './LoadingState';

describe('LoadingState', () => {
  it('exposes the default loading text as a status region', () => {
    render(<LoadingState />);
    expect(screen.getByRole('status')).toHaveTextContent('Cargando…');
  });

  it('shows a custom text when given one', () => {
    render(<LoadingState text="Cargando leads…" />);
    expect(screen.getByRole('status')).toHaveTextContent('Cargando leads…');
  });
});
