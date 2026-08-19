/** Shared shell pieces. One vocabulary for stats, controls and the three states
 *  every data view has to render, so the same idea never appears in two shapes. */

export function Stat({ label, value, sub, tone }) {
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <strong className={tone ? `stat-value ${tone}` : "stat-value"}>{value}</strong>
      {sub && <p className="stat-sub">{sub}</p>}
    </div>
  );
}

export function StatRow({ children }) {
  return <div className="stat-row">{children}</div>;
}

export function Field({ label, hint, children }) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Segmented({ label, options, value, onChange }) {
  return (
    <div className="segmented" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          className={value === option.value ? "segment on" : "segment"}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Provenance is a property of the data, so it renders as a line of text next
 *  to the data rather than as a warning banner at the top of the page. */
export function Provenance({ provenance }) {
  if (!provenance) return null;
  return (
    <p className={provenance.clean ? "provenance" : "provenance flagged"}>
      <strong>{provenance.month}.</strong> {provenance.note}
    </p>
  );
}

export function Loading({ label = "Loading" }) {
  return (
    <div className="loading" role="status">
      <span className="skeleton skeleton-line" />
      <span className="skeleton skeleton-line short" />
      <span className="visually-hidden">{label}</span>
    </div>
  );
}

export function ErrorState({ message, retry }) {
  return (
    <div className="error-state" role="alert">
      <p><strong>That view could not load.</strong> {message}</p>
      <p>If the store has not been built, run <code>uv run python scripts/build_db.py</code>.</p>
      {retry && <button type="button" onClick={retry}>Try again</button>}
    </div>
  );
}

export function Empty({ title, children }) {
  return (
    <div className="empty-state">
      <p><strong>{title}</strong></p>
      {children}
    </div>
  );
}

/** Wraps the loading / error / ready fork so no view reimplements it. */
export function Async({ state, children, label }) {
  if (state.error) return <ErrorState message={state.error} retry={state.retry} />;
  if (!state.data) return <Loading label={label} />;
  return (
    <div className={state.stale ? "is-stale" : undefined} aria-busy={state.stale || undefined}>
      {state.stale && <span className="visually-hidden" role="status">Refreshing this view</span>}
      {children(state.data)}
    </div>
  );
}

/** The technology stack, grouped, rendered from the single list in stack.js.
 *
 *  Each entry is a mark and a name. No version, because a version number is a
 *  fact about an environment rather than about the project, and the previous
 *  page carried fourteen of them for no reader's benefit. No description,
 *  because naming a tool and then explaining it is the tell of a page written
 *  for its author. */
export function TechStack({ stack, note, compact = false }) {
  return (
    <div className={compact ? "stack compact" : "stack"}>
      {stack.map((group) => (
        <section className="stack-group" key={group.category}>
          <h3>{group.category}</h3>
          <ul>
            {group.items.map((item) => (
              <li key={item.name}>
                {item.mark ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true" className="stack-mark">
                    <path d={item.mark.path} fill={item.mark.hex} />
                  </svg>
                ) : (
                  <span className="stack-mono" aria-hidden="true">
                    {item.name.split(" ").map((word) => word[0]).join("").slice(0, 3)}
                  </span>
                )}
                <span className="stack-name">{item.name}</span>
              </li>
            ))}
          </ul>
        </section>
      ))}
      {note && <p className="stack-note">{note}</p>}
    </div>
  );
}
