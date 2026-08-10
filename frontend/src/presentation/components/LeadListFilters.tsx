import { Search } from 'lucide-react';
import { LeadStatus, formatLeadStatusLabel } from '../../domain/lead.model';
import { Input } from './ui/Input';

interface LeadListFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  status: string;
  onStatusChange: (value: string) => void;
}

/** The search/filter toolbar, split out of the table so the table stays a pure renderer. */
export function LeadListFilters({ search, onSearchChange, status, onStatusChange }: LeadListFiltersProps) {
  return (
    <div className="flex flex-col sm:flex-row gap-4 justify-between items-center bg-slate-900/40 p-4 rounded-xl border border-slate-800">
      <div className="relative w-full sm:w-80">
        <Search className="w-4 h-4 absolute left-3 top-3 text-slate-500" aria-hidden="true" />
        <Input
          type="text"
          aria-label="Buscar leads"
          placeholder="Buscar por email, nombre o empresa..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="pl-9"
        />
      </div>

      <select
        aria-label="Filtrar por estado"
        value={status}
        onChange={(e) => onStatusChange(e.target.value)}
        className="w-full sm:w-auto bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 cursor-pointer"
      >
        <option value="">Todos los estados</option>
        {Object.values(LeadStatus).map((value) => (
          <option key={value} value={value}>
            {formatLeadStatusLabel(value)}
          </option>
        ))}
      </select>
    </div>
  );
}
