import { Layers } from 'lucide-react';
import * as groupsService from '../../application/services/groups.service';
import { usePaginated } from '../../application/data/use-paginated';
import { AsyncView } from '../components/ui/AsyncView';
import { Button } from '../components/ui/Button';
import { GroupForm } from '../components/GroupForm';
import { GroupRow } from '../components/GroupRow';

/** Sales groups: the teams an assignment rule can route to. Members are set from the advisors screen. */
export function GroupsPage() {
  const paginated = usePaginated((limit, offset) => groupsService.list(limit, offset));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Grupos</h2>
        <p className="text-sm text-slate-400">
          Equipos de asesores con una forma de reparto común. Una regla de asignación puede enviar sus leads a un grupo.
        </p>
      </div>

      {/* Outside AsyncView, like the advisors form: an empty organization must still be able to create one. */}
      <div className="bg-slate-900/40 p-6 rounded-xl border border-slate-800 space-y-4">
        <h3 className="font-bold text-slate-100 flex items-center gap-2">
          <Layers className="w-4 h-4 text-indigo-400" />
          Nuevo grupo
        </h3>
        <GroupForm
          submitLabel="Crear grupo"
          onSubmit={async (body) => {
            await groupsService.create(body);
            paginated.refetch();
          }}
        />
      </div>

      <AsyncView
        state={{ data: paginated.items, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText="Todavía no hay grupos."
        isEmpty={(items) => items.length === 0}
      >
        {(groups) => (
          <div className="space-y-4">
            <div className="bg-slate-900/40 rounded-xl border border-slate-800 overflow-hidden divide-y divide-slate-800">
              {groups.map((group) => (
                <GroupRow
                  key={group.id}
                  group={group}
                  onUpdate={async (id, body) => {
                    await groupsService.update(id, body);
                    paginated.refetch();
                  }}
                  onDelete={async (id) => {
                    await groupsService.remove(id);
                    paginated.refetch();
                  }}
                />
              ))}
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
