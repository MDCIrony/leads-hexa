import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AgentForm } from './AgentForm';

describe('AgentForm', () => {
  it('declares autocomplete on the password field so the browser stops warning about it', () => {
    render(<AgentForm groups={[]} onCreate={async () => {}} />);

    expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'new-password');
  });
});
