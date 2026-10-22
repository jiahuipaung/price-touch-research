import { NavLink, Route, Routes } from "react-router-dom";

import { useSnapshotStream } from "./api";
import { StatusBar } from "./components/StatusBar";
import { DataQuality } from "./views/DataQuality";
import { LiveMatrix } from "./views/LiveMatrix";
import { Methodology } from "./views/Methodology";
import { Research } from "./views/Research";

export default function App() {
  const stream = useSnapshotStream();
  return (
    <div className="app-shell">
      <header className="topbar"><NavLink className="brand" to="/"><span className="brand-mark">T</span><span><strong>TouchLab</strong><small>价格区间触达概率</small></span></NavLink><nav><NavLink to="/">实时矩阵</NavLink><NavLink to="/research">研究与回测</NavLink><NavLink to="/quality">数据质量</NavLink><NavLink to="/methodology">方法说明</NavLink></nav></header>
      <StatusBar snapshot={stream.snapshot} connection={stream.connection} />
      <main><Routes><Route path="/" element={<LiveMatrix snapshot={stream.snapshot} />} /><Route path="/research" element={<Research />} /><Route path="/quality" element={<DataQuality />} /><Route path="/methodology" element={<Methodology />} /></Routes></main>
      <footer>概率仅为研究估计，不构成交易建议 · schema v1.0</footer>
    </div>
  );
}
