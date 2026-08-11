export interface AttributeRow {
  key: string;
  value: string;
}

export type FieldErrors = Partial<
  Record<'firstName' | 'lastName' | 'company' | 'industry' | 'budget', string>
>;

export interface NewLeadFields {
  firstName: string;
  lastName: string;
  company: string;
  industry: string;
  budget: string;
}

// Client-side validation mirrors exactly what the ingest schema requires — required
// fields and the budget's type — because a 422 here never reaches the intake tray:
// the payload is rejected before it is ever persisted, and the user cannot recover it.
export function validate(fields: NewLeadFields): FieldErrors {
  const errors: FieldErrors = {};
  if (!fields.firstName.trim()) errors.firstName = 'Obligatorio.';
  if (!fields.lastName.trim()) errors.lastName = 'Obligatorio.';
  if (!fields.company.trim()) errors.company = 'Obligatorio.';
  if (!fields.industry.trim()) errors.industry = 'Obligatorio.';
  if (!fields.budget.trim()) errors.budget = 'Obligatorio.';
  else if (Number.isNaN(Number(fields.budget))) errors.budget = 'Tiene que ser un número.';
  return errors;
}

export function buildCustomAttributes(rows: AttributeRow[]): Record<string, unknown> {
  const entries = rows.filter((row) => row.key.trim() !== '').map((row) => [row.key, row.value] as const);
  return Object.fromEntries(entries);
}
