import { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { AsyncState } from '../../application/data/use-async';
import { usePaginated } from '../../application/data/use-paginated';
import { listMine } from '../../application/services/leads.service';
import type { LeadModel } from '../../domain/lead.model';
import { AsyncView } from '../components/ui/AsyncView';
import { Button } from '../components/ui/Button';
import { DashboardTable } from '../components/DashboardTable';
import { LeadListFilters } from '../components/LeadListFilters';

const leadDetailHref = (lead: LeadModel) => `/mis-leads/${lead.id}`;

/** The agent's own queue: read-only, server-filtered, sorted however /leads/mine returns it. */
export function MyLeadsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');

  const paginated = usePaginated<LeadModel>(
    (limit, offset) => listMine(limit, offset, { search: search || undefined, status: status || undefined }),
    { deps: [search, status] }
  );

  const state: AsyncState<LeadModel[]> = {
    data: paginated.items,
    error: paginated.error,
    loading: paginated.loading,
    refetch: paginated.refetch,
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Mis leads</h2>
        <p className="text-sm text-slate-400">Los leads que las reglas de asignación te repartieron.</p>
      </div>

      <LeadListFilters search={search} onSearchChange={setSearch} status={status} onStatusChange={setStatus} />

      <AsyncView
        state={state}
        isEmpty={(items) => items.length === 0}
        emptyText="No tienes leads asignados todavía."
      >
        {(items) => (
          <div className="space-y-4">
            <DashboardTable leads={items} getDetailHref={leadDetailHref} />
            <div className="flex items-center justify-between text-sm text-slate-400">
              <span>{paginated.total} leads en total</span>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  onClick={paginated.previousPage}
                  disabled={paginated.page === 0}
                  aria-label="Página anterior"
                >
                  <ChevronLeft className="w-4 h-4" />
                </Button>
                <Button
                  variant="secondary"
                  onClick={paginated.nextPage}
                  disabled={!paginated.hasMore}
                  aria-label="Página siguiente"
                >
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        )}
      </AsyncView>
    </div>
  );
}
