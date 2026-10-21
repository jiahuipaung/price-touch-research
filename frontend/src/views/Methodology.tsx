export function Methodology() {
  return (
    <article className="methodology panel">
      <p className="eyebrow">Auditable definition</p><h2>What one cell means</h2>
      <p className="lead">在该观测时间窗内，任一时刻的成交价落入该价格区间，即记为一次触达；不要求收盘价位于区间内。</p>
      <div className="method-grid"><section><h3>Geometry</h3><p>Price cells use half-open bounds <code>[lower, upper)</code>. Time windows are also half-open, begin at origin +5s, and never overlap. Every forecast freezes its own origin, price bounds and time bounds.</p></section><section><h3>Estimator</h3><p>A deterministic seeded block bootstrap is primary. A diffusion model supplies the baseline and the bounded fallback. Isotonic calibration only consumes labels mature before the forecast cutoff.</p></section><section><h3>Assumptions</h3><p>Recent return blocks approximate near-future path structure; tick sizes and market calendars are configured per instrument; a quote-only commodity source is explicitly marked DELAYED.</p></section><section><h3>Limitations</h3><p>No model removes tail risk. Jump gaps may skip intermediate price intervals. BAR_APPROX labels overstate within-bar path knowledge. Data outages pause evidence rather than being silently imputed.</p></section></div>
    </article>
  );
}
