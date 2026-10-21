import { useMemo, useState } from "react";

import type { ForecastSnapshot } from "../types";

interface Props {
  snapshot?: ForecastSnapshot;
}

interface CellSelection {
  row: number;
  column: number;
}

function colorForProbability(value: number): string {
  const lightness = 12 + value * 48;
  return `hsl(167 72% ${lightness}%)`;
}

export function LiveMatrix({ snapshot }: Props) {
  const [selection, setSelection] = useState<CellSelection | undefined>();
  const [intervalCount, setIntervalCount] = useState(snapshot?.intervals.length ?? 21);
  const validation = intervalCount % 2 === 0 ? "Interval count must be odd" : undefined;
  const selected = useMemo(() => {
    if (!snapshot || !selection) return undefined;
    return {
      interval: snapshot.intervals[selection.row],
      window: snapshot.windows[selection.column],
      baseline: snapshot.matrices.baseline[selection.row][selection.column],
      raw: snapshot.matrices.raw[selection.row][selection.column],
      calibrated: snapshot.matrices.calibrated[selection.row][selection.column],
    };
  }, [selection, snapshot]);

  if (!snapshot) return <section className="empty-state">Awaiting a complete probability matrix…</section>;
  return (
    <div className="live-layout">
      <section className="panel matrix-panel">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">Every second · full refresh</p>
            <h2>{snapshot.instrument} touch surface</h2>
          </div>
          <div className="controls">
            <label>Asset<select aria-label="Asset" value={snapshot.asset} onChange={() => undefined}><option>{snapshot.asset}</option></select></label>
            <label>Interval count<input aria-label="Interval count" type="number" value={intervalCount} onChange={(event) => setIntervalCount(Number(event.target.value))} /></label>
          </div>
        </header>
        {validation && <p role="alert" className="validation">{validation}</p>}
        <div className="matrix-scroll">
          <div className="matrix" style={{ gridTemplateColumns: `8.5rem repeat(${snapshot.windows.length}, minmax(4.3rem, 1fr))` }}>
            <div className="axis-corner">price \ horizon</div>
            {snapshot.windows.map((window) => <div className="axis-label" key={window.index}>+{(window.end_ns - snapshot.windows[0].start_ns) / 1e9}s</div>)}
            {snapshot.intervals.map((interval, row) => [
              <div className="price-label" key={`label-${interval.index}`}>{interval.lower_ticks}–{interval.upper_ticks}</div>,
              ...snapshot.windows.map((window, column) => {
                const value = snapshot.matrices.calibrated[row][column];
                return <button data-testid="matrix-cell" className="matrix-cell" key={`${interval.index}-${window.index}`} style={{ background: colorForProbability(value) }} onClick={() => setSelection({ row, column })}>{(value * 100).toFixed(1)}%</button>;
              }),
            ])}
          </div>
        </div>
        <div className="legend"><span>0%</span><div className="legend-gradient"/><span>100%</span><small>Fixed scale across refreshes</small></div>
      </section>
      <aside className="panel inspector">
        <p className="eyebrow">Frozen cell evidence</p>
        <h2>Cell inspector</h2>
        {selected ? <>
          <dl>
            <div><dt>Interval [lower, upper)</dt><dd>{selected.interval.lower_ticks} — {selected.interval.upper_ticks}</dd></div>
            <div><dt>Window [start, end)</dt><dd>{selected.window.start_ns} — {selected.window.end_ns}</dd></div>
          </dl>
          <div className="probability-stack">
            <p>Baseline <strong>{(selected.baseline * 100).toFixed(2)}%</strong></p>
            <p>Raw <strong>{(selected.raw * 100).toFixed(2)}%</strong></p>
            <p>Calibrated <strong>{(selected.calibrated * 100).toFixed(2)}%</strong></p>
          </div>
        </> : <p>Select a cell to inspect its frozen price and time bounds.</p>}
        <div className="flag-list">{snapshot.quality_flags.map((flag) => <span className="badge" key={flag}>{flag}</span>)}</div>
      </aside>
    </div>
  );
}
