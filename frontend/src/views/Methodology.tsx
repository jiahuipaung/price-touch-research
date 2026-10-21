export function Methodology() {
  return (
    <article className="methodology panel">
      <p className="eyebrow">可审计定义</p><h2>一个格子代表什么</h2>
      <p className="lead">在该观测时间窗内，任一时刻的成交价落入该价格区间，即记为一次触达；不要求收盘价位于区间内。</p>
      <div className="method-grid"><section><h3>区间与时间窗</h3><p>价格格采用半开区间 <code>[lower, upper)</code>。时间窗同样半开，从预测原点 +5 秒开始且互不重叠。每次预测都会冻结自己的原点、价格边界和时间边界。</p></section><section><h3>估计方法</h3><p>主模型是带确定性种子的分块 Bootstrap；扩散模型提供可解释基线和有界降级。等距校准只使用在预测截止时刻之前已经成熟的标签。</p></section><section><h3>假设 Assumptions</h3><p>近期收益块可近似短期路径结构；tick 精度和市场日历按品种配置；仅提供报价的商品数据源会明确标记为 DELAYED。</p></section><section><h3>限制 Limitations</h3><p>任何模型都不能消除尾部风险。跳空可能越过中间价格区间；BAR_APPROX 无法还原 K 线内部路径；数据中断时暂停新证据，不做静默插值。</p></section></div>
    </article>
  );
}
