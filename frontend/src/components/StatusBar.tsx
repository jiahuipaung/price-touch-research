import type { ConnectionState } from "../state";
import type { ForecastSnapshot } from "../types";

interface Props {
  snapshot?: ForecastSnapshot;
  connection: ConnectionState;
}

export function StatusBar({ snapshot, connection }: Props) {
  if (!snapshot) {
    return <div className="status-bar waiting">{connection} · waiting for first complete snapshot</div>;
  }
  const stateFlags = [
    snapshot.source.mode,
    ...(snapshot.source.stale ? ["STALE"] : []),
    ...(snapshot.source.market_closed ? ["MARKET_CLOSED"] : []),
    ...snapshot.quality_flags,
  ];
  return (
    <section className="status-bar" aria-label="Runtime status">
      <div className="status-badges">
        {[...new Set(stateFlags)].map((flag) => (
          <span className={`badge badge-${flag.toLowerCase()}`} key={flag}>
            {flag}
          </span>
        ))}
      </div>
      <dl className="status-facts">
        <div><dt>Connection</dt><dd>{connection}</dd></div>
        <div><dt>Source age</dt><dd>{snapshot.source.age_seconds.toFixed(2)}s</dd></div>
        <div><dt>Provider</dt><dd>{snapshot.source.provider}</dd></div>
        <div><dt>Model</dt><dd>{snapshot.model_version}</dd></div>
        <div><dt>Paths</dt><dd>{snapshot.path_count.toLocaleString()}</dd></div>
      </dl>
    </section>
  );
}
