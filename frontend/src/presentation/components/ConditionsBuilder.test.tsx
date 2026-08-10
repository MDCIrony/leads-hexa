import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Operator, type CriterionModel } from '../../domain/rule.model';
import { ConditionsBuilder } from './ConditionsBuilder';

const CONDITIONS: CriterionModel[] = [{ field: 'budget', operator: Operator.GREATER_THAN, value: 5000 }];

describe('ConditionsBuilder', () => {
  it('offers only operators from the generated Operator enum', () => {
    render(<ConditionsBuilder conditions={CONDITIONS} onChange={vi.fn()} />);

    const select = screen.getByDisplayValue(Operator.GREATER_THAN);
    const options = Array.from(select.querySelectorAll('option')).map((o) => o.getAttribute('value'));

    expect(options.sort()).toEqual(Object.values(Operator).sort());
  });

  it('sends value as null for a valueless operator like IS_EMPTY', async () => {
    const onChange = vi.fn();
    render(<ConditionsBuilder conditions={CONDITIONS} onChange={onChange} />);

    await userEvent.selectOptions(screen.getByDisplayValue(Operator.GREATER_THAN), Operator.IS_EMPTY);

    expect(onChange).toHaveBeenCalledWith([{ field: 'budget', operator: Operator.IS_EMPTY, value: null }]);
  });

  it('parses an IN value as a trimmed list, not a single string', async () => {
    const conditions: CriterionModel[] = [{ field: 'industry', operator: Operator.IN, value: [] }];
    const onChange = vi.fn();
    render(<ConditionsBuilder conditions={conditions} onChange={onChange} />);

    fireEvent.change(screen.getByPlaceholderText('a, b, c'), { target: { value: 'Tech, Finance' } });

    expect(onChange).toHaveBeenLastCalledWith([{ field: 'industry', operator: Operator.IN, value: ['Tech', 'Finance'] }]);
  });
});
