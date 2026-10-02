import * as advisorsService from '../../application/services/advisors.service';
import { useAsync } from '../../application/data/use-async';
import { AsyncView } from './ui/AsyncView';

// ponytail: first 100 members only; page it if a group outgrows that.
const MEMBERS_PAGE = 100;

/** A group's members come from lead-core's /advisors: identity's /agents knows nothing of groups. */
export function GroupMembers({ groupId }: { groupId: string }) {
  const state = useAsync(() => advisorsService.list(MEMBERS_PAGE, 0, { groupId }), [groupId]);

  return (
    <AsyncView
      state={state}
      loadingText="Cargando miembros…"
      emptyText="Este grupo no tiene asesores. Asígnalos desde la pantalla de Asesores."
      isEmpty={(page) => page.items.length === 0}
    >
      {(page) => (
        <ul className="divide-y divide-slate-800 rounded-lg border border-slate-800">
          {page.items.map((member) => (
            <li key={member.agentId} className="px-3 py-2 flex items-center justify-between text-sm">
              <span className="text-slate-200">{member.name}</span>
              <span className="text-xs text-slate-400">
                {member.activeLoad} leads activos{member.isActive ? '' : ' • Inactivo'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </AsyncView>
  );
}
