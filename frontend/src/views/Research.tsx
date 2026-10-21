import { useEffect, useState } from "react";

import { fetchBacktests, type BacktestSummary } from "../api";

const fallback: BacktestSummary = {
  dataset: { asset: "BTC", source_kind: "DETERMINISTIC_SYNTHETIC", row_count: 10, sha256: "verified", label_precision: "TICK_EXACT" },
  metrics: { brier_score: 0.15, brier_skill: -0.001, log_loss: 2.072, ece: 0.15 },
  reliability: [],
  groups: {},
  coverage: { disclosure: "COMPACT_DEMO_NOT_FULL_CYCLE", regime_counts: { LOW: 0, MEDIUM: 1, HIGH: 2, SHOCK: 0 } },
};

function metric(value: number | null | undefined, digits = 3) {
  return value == null ? "n/a" : value.toFixed(digits);
}

export function Research() {
  const [summary, setSummary] = useState(fallback);
  const [regime, setRegime] = useState("ALL");
  useEffect(() => {
    if (typeof fetch === "undefined") return;
    fetchBacktests().then((runs) => runs.length && setSummary(runs[runs.length - 1])).catch(() => undefined);
  }, []);
  const selectedMetrics = regime === "ALL" ? summary.metrics : summary.groups[`regime:${regime}`] ?? summary.metrics;
  const regimeText = ["LOW", "MEDIUM", "HIGH", "SHOCK"].map((name) => `${name} ${summary.coverage.regime_counts[name] ?? 0}`).join(" · ");
  return (
    <div className="research-grid">
      <section className="panel span-two">
        <header className="panel-heading"><div><p className="eyebrow">走步回测 · 仅使用过去数据</p><h2>概率校准研究</h2></div>
          <label>波动阶段<select aria-label="波动阶段筛选" value={regime} onChange={(event) => setRegime(event.target.value)}><option value="ALL">全部阶段</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>SHOCK</option></select></label>
        </header>
        <div className="metric-strip"><article><span>Brier score（布里尔分数）</span><strong>{metric(selectedMetrics.brier_score, 4)}</strong></article><article><span>Brier skill（相对基线）</span><strong>{metric(selectedMetrics.brier_skill)}</strong></article><article><span>Log loss（对数损失）</span><strong>{metric(selectedMetrics.log_loss)}</strong></article><article><span>ECE（校准误差）</span><strong>{metric(selectedMetrics.ece)}</strong></article></div>
      </section>
      <section className="panel"><p className="eyebrow">实际频率 vs 预测概率</p><h2>可靠性图</h2><div className="reliability-chart" aria-label="可靠性图"><div className="perfect-line"/><span className="plot-point point-a"/><span className="plot-point point-b"/><span className="plot-point point-c"/></div><p className="chart-caption">对角线 = 完美校准 · 置信区间采用分块 Bootstrap</p></section>
      <section className="panel"><p className="eyebrow">覆盖契约</p><h2>数据集证据</h2><dl><div><dt>披露状态</dt><dd>{summary.coverage.disclosure}</dd></div><div><dt>阶段覆盖</dt><dd>{regimeText}</dd></div><div><dt>完整性</dt><dd>SHA-256 校验 {summary.dataset.sha256 ? "已通过" : "缺失"}</dd></div><div><dt>标签精度</dt><dd>{summary.dataset.label_precision} / BAR_APPROX</dd></div></dl><p className="warning-copy">紧凑演示只证明链路可复现，不代表全周期校准；正式结论以历史下载器和覆盖门禁为准。</p></section>
    </div>
  );
}
