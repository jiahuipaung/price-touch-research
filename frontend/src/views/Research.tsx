export function Research() {
  return (
    <div className="research-grid">
      <section className="panel span-two">
        <header className="panel-heading"><div><p className="eyebrow">Walk-forward · past-only</p><h2>Calibration research</h2></div>
          <label>Regime filter<select aria-label="Regime filter"><option>All regimes</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>SHOCK</option></select></label>
        </header>
        <div className="metric-strip"><article><span>Brier score</span><strong>0.1500</strong></article><article><span>Brier skill</span><strong>−0.10%</strong></article><article><span>Log loss</span><strong>2.072</strong></article><article><span>ECE</span><strong>0.150</strong></article></div>
      </section>
      <section className="panel"><p className="eyebrow">Observed vs predicted</p><h2>Reliability diagram</h2><div className="reliability-chart" aria-label="Reliability diagram plot"><div className="perfect-line"/><span className="plot-point point-a"/><span className="plot-point point-b"/><span className="plot-point point-c"/></div><p className="chart-caption">Diagonal = perfect calibration · block-bootstrap confidence intervals</p></section>
      <section className="panel"><p className="eyebrow">Coverage contract</p><h2>Dataset evidence</h2><dl><div><dt>Disclosure</dt><dd>COMPACT_DEMO_NOT_FULL_CYCLE</dd></div><div><dt>Regime coverage</dt><dd>LOW · MEDIUM · HIGH · SHOCK</dd></div><div><dt>Integrity</dt><dd>SHA-256 checksum verified</dd></div><div><dt>Label precision</dt><dd>TICK_EXACT / BAR_APPROX</dd></div></dl><p className="warning-copy">Demo numbers prove the pipeline, not full-cycle calibration. Use the history downloader before acceptance claims.</p></section>
    </div>
  );
}
