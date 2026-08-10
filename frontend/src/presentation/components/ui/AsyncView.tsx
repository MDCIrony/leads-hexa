import type { ReactNode } from 'react';
import type { AsyncState } from '../../../application/data/use-async';
import { LoadingState } from './LoadingState';
import { ErrorState } from './ErrorState';
import { EmptyState } from './EmptyState';

interface AsyncViewProps<T> {
  state: AsyncState<T>;
  children: (data: T) => ReactNode;
  loadingText?: string;
  emptyText?: string;
  emptyAction?: { label: string; onClick: () => void };
  /**
   * Tells "empty" apart from "loaded": a list with zero items is empty, a
   * detail that loaded successfully is not, even though both can be
   * non-null. Defaults to treating `null` data as empty, which only fires
   * for detail views whose type allows a legitimate null result.
   */
  isEmpty?: (data: T) => boolean;
}

/** Renders the one loading/error/empty/data branch every view over useAsync would otherwise repeat. */
export function AsyncView<T>({
  state,
  children,
  loadingText,
  emptyText = 'No hay nada que mostrar.',
  emptyAction,
  isEmpty = (data) => data === null,
}: AsyncViewProps<T>) {
  const { data, error, loading, refetch } = state;

  if (loading) return <LoadingState text={loadingText} />;
  if (error) return <ErrorState error={error} onRetry={refetch} />;
  if (data === null || isEmpty(data)) return <EmptyState text={emptyText} action={emptyAction} />;

  return <>{children(data)}</>;
}
