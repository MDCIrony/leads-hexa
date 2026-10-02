import { useState } from 'react';
import * as agentsService from '../../application/services/agents.service';
import * as advisorsService from '../../application/services/advisors.service';
import * as groupsService from '../../application/services/groups.service';
import * as rosterService from '../../application/services/agent-roster.service';
import { useAsync } from '../../application/data/use-async';
import { usePaginated } from '../../application/data/use-paginated';
import { useSession } from '../../application/session/use-session';
import { AsyncView } from '../components/ui/AsyncView';
import { AgentSettings } from '../components/AgentSettings';
import { AgentForm } from '../components/AgentForm';
import { Button } from '../components/ui/Button';

/**
 * GET /agents only returns active agents when `is_active` is absent — the
 * checkbox is the only way to reach a deactivated one and reactivate it.
 */
export function AgentsPage() {
  const [showInactive, setShowInactive] = useState(false);
  const { user } = useSession();

  const paginated = usePaginated(
    (limit, offset) => rosterService.listRoster(limit, offset, showInactive ? { isActive: false } : {}),
    { deps: [showInactive] }
  );
  // A failed groups fetch only leaves "Sin grupo" to pick; it shouldn't block managing accounts.
  const { data: groupsPage } = useAsync(() => groupsService.list(100, 0), []);

  // The endpoint takes no role filter, so it hands back the whole organization,
  // signed-in manager included. Nobody deactivates themselves from this screen.
  const others = paginated.items.filter(({ agent }) => agent.id !== user?.id);
  const groups = groupsPage?.items ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-100">Asesores</h2>
          <p className="text-sm text-slate-400">Alta, edición y control de acceso de los asesores de la organización.</p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded border-slate-700 bg-slate-950"
          />
          Ver desactivados
        </label>
      </div>

      {/* Outside AsyncView: a refetch shows the loading state, which would unmount the form and its error. */}
      <AgentForm
        groups={groups}
        onCreate={async (body, groupId) => {
          // Refetched even when the group step fails: the agent exists and belongs in the list.
          try {
            await rosterService.createWithGroup(body, groupId);
          } finally {
            paginated.refetch();
          }
        }}
      />

      <AsyncView
        state={{ data: others, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText={showInactive ? 'No hay asesores desactivados.' : 'No hay asesores activos.'}
        isEmpty={(items) => items.length === 0}
      >
        {(entries) => (
          <div className="space-y-4">
            <AgentSettings
              entries={entries}
              groups={groups}
              onUpdate={async (id, body) => {
                await agentsService.update(id, body);
                paginated.refetch();
              }}
              onDeactivate={async (id) => {
                await agentsService.deactivate(id);
                paginated.refetch();
              }}
              onReactivate={async (id) => {
                await agentsService.update(id, { is_active: true });
                paginated.refetch();
              }}
              onChangeGroup={async (id, groupId) => {
                await advisorsService.setGroup(id, groupId);
                paginated.refetch();
              }}
            />

            <div className="flex items-center justify-between text-sm text-slate-400">
              <span>
                {/* The signed-in manager is active by definition, so they only inflate the active listing. */}
                Página {paginated.page + 1} • {showInactive ? paginated.total : paginated.total - 1} en total
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={paginated.previousPage} disabled={paginated.page === 0}>
                  Anterior
                </Button>
                <Button variant="secondary" onClick={paginated.nextPage} disabled={!paginated.hasMore}>
                  Siguiente
                </Button>
              </div>
            </div>
          </div>
        )}
      </AsyncView>
    </div>
  );
}
