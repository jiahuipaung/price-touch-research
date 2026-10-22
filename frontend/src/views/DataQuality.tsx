export function DataQuality() {
  return (
    <div className="quality-layout">
      <section className="panel"><p className="eyebrow">数据接入护栏</p><h2>质量计数器</h2><div className="counter-grid"><article><strong>0</strong><span>重复事件</span></article><article><strong>0</strong><span>过晚事件</span></article><article><strong>0</strong><span>非法价格</span></article><article><strong>0</strong><span>时钟偏差</span></article></div></section>
      <section className="panel"><p className="eyebrow">不静默降级</p><h2>中断 / 重连时间线</h2><ol className="timeline"><li><time>08:00:00</time><div><strong>HEALTHY</strong><p>回放数据源已连接，事件水位持续推进。</p></div></li><li><time>08:02:14</time><div><strong>GAP</strong><p>预测明确暂停；旧快照不会伪装成新 forecast ID。</p></div></li><li><time>08:02:17</time><div><strong>RECOVERED</strong><p>数据源在有界重连后恢复。</p></div></li></ol></section>
    </div>
  );
}
