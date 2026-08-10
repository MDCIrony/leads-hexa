import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { EmptyState } from './EmptyState';

describe('EmptyState', () => {
  it('shows the given text', () => {
    render(<EmptyState text="No hay leads." />);
    expect(screen.getByText('No hay leads.')).toBeInTheDocument();
  });

  it('omits the action button when none is given', () => {
    render(<EmptyState text="No hay leads." />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('runs the action when its button is clicked', async () => {
    const onClick = vi.fn();
    render(<EmptyState text="No hay leads." action={{ label: 'Crear lead', onClick }} />);

    await userEvent.click(screen.getByRole('button', { name: 'Crear lead' }));

    expect(onClick).toHaveBeenCalledOnce();
  });
});
