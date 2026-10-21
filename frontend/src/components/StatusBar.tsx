import type { ConnectionState } from "../state";
import type { ForecastSnapshot } from "../types";

interface Props {
  snapshot?: ForecastSnapshot;
  connection: ConnectionState;
}

export function StatusBar({ snapshot, connection }: Props) {
  if (!snapshot) {
    return <div className="status-bar waiting">{connection} · 等待首个完整快照</div>;
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
        <div><dt>连接状态</dt><dd>{connection}</dd></div>
        <div><dt>数据延迟</dt><dd>{snapshot.source.age_seconds.toFixed(2)}s</dd></div>
        <div><dt>数据来源</dt><dd>{snapshot.source.provider}</dd></div>
        <div><dt>模型版本</dt><dd>{snapshot.model_version}</dd></div>
        <div><dt>模拟路径</dt><dd>{snapshot.path_count.toLocaleString()}</dd></div>
      </dl>
    </section>
  );
}
