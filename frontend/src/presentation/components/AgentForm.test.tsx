import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { AgentForm } from './AgentForm';

describe('AgentForm', () => {
  it('declares autocomplete on the password field so the browser stops warning about it', () => {
    render(<AgentForm groups={[]} onCreate={async () => {}} />);

    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'new-password');
  });

  it('offers no role choice and always registers an advisor', async () => {
    const onCreate = vi.fn().mockResolvedValue(undefined);
    render(<AgentForm groups={[]} onCreate={onCreate} />);

    expect(screen.queryByLabelText('Rol')).not.toBeInTheDocument();

    await userEvent.type(screen.getByLabelText('Nombre completo'), 'Asesor 01');
    await userEvent.type(screen.getByLabelText('Correo'), 'asesor@example.com');
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secret123');
    await userEvent.click(screen.getByRole('button', { name: 'Guardar asesor' }));

    expect(onCreate).toHaveBeenCalledWith(expect.objectContaining({ role: 'AGENT' }), null);
  });
});
