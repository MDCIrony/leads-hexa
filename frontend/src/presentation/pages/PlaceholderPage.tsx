interface PlaceholderPageProps {
  title: string;
}

/** Stands in for a view not built yet; the route it fills already exists, is protected, and navigates. */
export function PlaceholderPage({ title }: PlaceholderPageProps) {
  return (
    <div className="p-6 text-slate-400">
      <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
      <p>Vista pendiente.</p>
    </div>
  );
}
