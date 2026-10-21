export function DataQuality() {
  return (
    <div className="quality-layout">
      <section className="panel"><p className="eyebrow">Ingestion guardrail</p><h2>Quality counters</h2><div className="counter-grid"><article><strong>0</strong><span>Duplicate events</span></article><article><strong>0</strong><span>Too-late events</span></article><article><strong>0</strong><span>Invalid prices</span></article><article><strong>0</strong><span>Clock skew</span></article></div></section>
      <section className="panel"><p className="eyebrow">No silent fallback</p><h2>Gap / reconnect timeline</h2><ol className="timeline"><li><time>08:00:00</time><div><strong>HEALTHY</strong><p>Replay source connected; event watermark advancing.</p></div></li><li><time>08:02:14</time><div><strong>GAP</strong><p>Forecasts visibly paused; no stale snapshot received a new ID.</p></div></li><li><time>08:02:17</time><div><strong>RECOVERED</strong><p>Source resumed after bounded reconnect.</p></div></li></ol></section>
    </div>
  );
}
