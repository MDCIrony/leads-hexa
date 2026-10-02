import * as rulesService from '../../application/services/rules.service';
import * as agentsService from '../../application/services/agents.service';
import * as groupsService from '../../application/services/groups.service';
import { useAsync } from '../../application/data/use-async';
import { usePaginated } from '../../application/data/use-paginated';
import { AsyncView } from '../components/ui/AsyncView';
import { Button } from '../components/ui/Button';
import { AssignmentRuleForm } from '../components/AssignmentRuleForm';
import { AssignmentRuleRow } from '../components/AssignmentRuleRow';

/** Rules evaluate by priority and the list already arrives sorted that way — never re-sorted here. */
export function AssignmentRulesPage() {
  // A failed or slow fetch of either target list shouldn't block the rules themselves.
  const { data: agentsPage } = useAsync(() => agentsService.list(100, 0), []);
  const agents = agentsPage?.items ?? [];
  const { data: groupsPage } = useAsync(() => groupsService.list(100, 0), []);
  const groups = groupsPage?.items ?? [];

  const paginated = usePaginated((limit, offset) => rulesService.assignment.list(limit, offset));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Reglas de asignación</h2>
        <p className="text-sm text-slate-400">
          Reparten un lead puntuado a un grupo o a asesores concretos según su rango de puntuación. Se evalúan en orden de prioridad.
        </p>
      </div>

      <AssignmentRuleForm
        agents={agents}
        groups={groups}
        onCreate={async (body) => {
          await rulesService.assignment.create(body);
          paginated.refetch();
        }}
      />

      <AsyncView
        state={{ data: paginated.items, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText="No hay reglas de asignación configuradas."
        isEmpty={(items) => items.length === 0}
      >
        {(rules) => (
          <div className="space-y-4">
            <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden">
              <div className="p-4 border-b border-slate-800 text-xs font-semibold text-slate-400 uppercase">
                Reglas, por prioridad
              </div>
              <div className="divide-y divide-slate-800">
                {rules.map((rule) => (
                  <AssignmentRuleRow
                    key={rule.id}
                    rule={rule}
                    agents={agents}
                    groups={groups}
                    onUpdate={async (id, body) => {
                      await rulesService.assignment.update(id, body);
                      paginated.refetch();
                    }}
                    onDelete={async (id) => {
                      await rulesService.assignment.remove(id);
                      paginated.refetch();
                    }}
                  />
                ))}
              </div>
            </div>

            <div className="flex items-center justify-between text-sm text-slate-400">
              <span>
                Página {paginated.page + 1} • {paginated.total} en total
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
