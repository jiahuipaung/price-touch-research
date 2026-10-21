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
  const validation = intervalCount % 2 === 0 ? "价格区间数量必须为奇数" : undefined;
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

  if (!snapshot) return <section className="empty-state">正在等待完整概率矩阵…</section>;
  return (
    <div className="live-layout">
      <section className="panel matrix-panel">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">每秒 · 整体重新估计</p>
            <h2>{snapshot.instrument} 触达概率矩阵</h2>
          </div>
          <div className="controls">
            <label>资产<select aria-label="资产" value={snapshot.asset} onChange={() => undefined}><option>{snapshot.asset}</option></select></label>
            <label>区间数量<input aria-label="区间数量" type="number" value={intervalCount} onChange={(event) => setIntervalCount(Number(event.target.value))} /></label>
          </div>
        </header>
        {validation && <p role="alert" className="validation">{validation}</p>}
        <div className="matrix-scroll">
          <div className="matrix" style={{ gridTemplateColumns: `8.5rem repeat(${snapshot.windows.length}, minmax(4.3rem, 1fr))` }}>
            <div className="axis-corner">价格 \ 未来时间</div>
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
        <div className="legend"><span>0%</span><div className="legend-gradient"/><span>100%</span><small>跨刷新固定色标</small></div>
      </section>
      <aside className="panel inspector">
        <p className="eyebrow">冻结边界证据</p>
        <h2>格子详情</h2>
        {selected ? <>
          <dl>
            <div><dt>价格区间 [下界, 上界)</dt><dd>{selected.interval.lower_ticks} — {selected.interval.upper_ticks}</dd></div>
            <div><dt>时间窗 [开始, 结束)</dt><dd>{selected.window.start_ns} — {selected.window.end_ns}</dd></div>
          </dl>
          <div className="probability-stack">
            <p>基线 Baseline <strong>{(selected.baseline * 100).toFixed(2)}%</strong></p>
            <p>原始 Raw <strong>{(selected.raw * 100).toFixed(2)}%</strong></p>
            <p>校准后 Calibrated <strong>{(selected.calibrated * 100).toFixed(2)}%</strong></p>
          </div>
        </> : <p>选择任一格，查看该预测签发时冻结的价格与时间边界。</p>}
        <div className="flag-list">{snapshot.quality_flags.map((flag) => <span className="badge" key={flag}>{flag}</span>)}</div>
      </aside>
    </div>
  );
}
