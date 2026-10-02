import type { SelectHTMLAttributes } from 'react';
import type { Group } from '../../application/services/groups.service';
import { Select } from './ui/Select';

interface GroupSelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'value' | 'onChange'> {
  groups: Group[];
  value: string | null;
  onChange: (groupId: string | null) => void;
  /** Injected by Field, like Input's. */
  hasError?: boolean;
  /** false hides "Sin grupo" where the API cannot take the group back, e.g. a rule's PATCH. */
  allowNone?: boolean;
}

/** Sales group picker: the empty option means no group, sent as null. */
export function GroupSelect({ groups, value, onChange, allowNone = true, ...rest }: GroupSelectProps) {
  return (
    <Select value={value ?? ''} onChange={(e) => onChange(e.target.value || null)} {...rest}>
      {allowNone && <option value="">Sin grupo</option>}
      {groups.map((group) => (
        <option key={group.id} value={group.id}>
          {group.name}
        </option>
      ))}
    </Select>
  );
}
