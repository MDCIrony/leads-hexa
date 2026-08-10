import * as rulesService from '../../application/services/rules.service';
import { usePaginated } from '../../application/data/use-paginated';
import { AsyncView } from '../components/ui/AsyncView';
import { Button } from '../components/ui/Button';
import { RuleBuilderForm } from '../components/RuleBuilderForm';
import { ScoringRuleRow } from '../components/ScoringRuleRow';

/** Rules evaluate by priority and the list already arrives sorted that way — never re-sorted here. */
export function ScoringRulesPage() {
  const paginated = usePaginated((limit, offset) => rulesService.scoring.list(limit, offset));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Reglas de puntuación</h2>
        <p className="text-sm text-slate-400">
          Suman o restan puntos a un lead según sus condiciones. Se evalúan en orden de prioridad.
        </p>
      </div>

      <RuleBuilderForm
        onCreate={async (body) => {
          await rulesService.scoring.create(body);
          paginated.refetch();
        }}
      />

      <AsyncView
        state={{ data: paginated.items, error: paginated.error, loading: paginated.loading, refetch: paginated.refetch }}
        emptyText="No hay reglas de puntuación configuradas."
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
                  <ScoringRuleRow
                    key={rule.id}
                    rule={rule}
                    onUpdate={async (id, body) => {
                      await rulesService.scoring.update(id, body);
                      paginated.refetch();
                    }}
                    onDelete={async (id) => {
                      await rulesService.scoring.remove(id);
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
