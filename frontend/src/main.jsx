import { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity, AlertTriangle, ArrowDownRight, ArrowUpRight, Bot, Box, BrainCircuit,
  Check, ChevronRight, CircleHelp, ClipboardCheck, Database, FileText, Gauge,
  LayoutDashboard, LoaderCircle, Menu, MessageSquareText, PackageSearch, RefreshCw,
  Search, Send, ServerCog, ShieldCheck, Sparkles, TrendingUp, Truck, X, Zap,
} from "lucide-react";
import "./styles.css";

const navItems = [
  { id: "dashboard", label: "Command center", icon: LayoutDashboard },
  { id: "inventory", label: "Inventory explorer", icon: PackageSearch },
  { id: "suppliers", label: "Supplier pulse", icon: Truck },
  { id: "policy", label: "Policy copilot", icon: MessageSquareText },
];

const statusLabel = { ready: "Connected", configured: "Configured", offline: "Offline", missing: "Needs setup", unknown: "Unknown" };

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || "Something went wrong.");
  return payload;
}

function useApi(path, initialValue) {
  const [data, setData] = useState(initialValue);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = async () => {
    setLoading(true);
    setError("");
    try { setData(await api(path)); } catch (err) { setError(err.message); } finally { setLoading(false); }
  };
  useEffect(() => { reload(); }, [path]);
  return { data, loading, error, reload };
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
}

function formatNumber(value) { return new Intl.NumberFormat("en-IN").format(Number(value || 0)); }

function getSeverity(item) {
  if (item.slob_flag === "OBSOLETE") return "critical";
  if (item.current_stock < item.policy_reorder_point || item.slob_flag === "SLOW_MOVER") return "watch";
  return "healthy";
}

function StatusRail({ health, onRefresh }) {
  const services = health ? Object.entries(health) : [];
  return <section className="status-rail" aria-label="System status">
    <div className="status-intro"><ServerCog size={16} /><span>System readiness</span></div>
    <div className="status-services">
      {services.map(([key, service]) => <div className="service-status" key={key} title={service.label}>
        <span className={`status-dot ${service.state}`} />
        <span>{key === "rapids" ? "RAPIDS" : key === "nim" ? "NIM" : key === "retrieval" ? "NeMo Retriever" : "Data"}</span>
        <b>{statusLabel[service.state]}</b>
      </div>)}
    </div>
    <button className="icon-button" onClick={onRefresh} title="Refresh system status"><RefreshCw size={16} /></button>
  </section>;
}

function Metric({ label, value, subtext, tone = "lime", icon: Icon }) {
  return <article className={`metric-card ${tone}`}>
    <div className="metric-top"><span>{label}</span><div className="metric-icon"><Icon size={18} /></div></div>
    <strong>{value}</strong>
    <small>{subtext}</small>
  </article>;
}

function SectionHeader({ eyebrow, title, detail, action }) {
  return <div className="section-header">
    <div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{detail && <p>{detail}</p>}</div>
    {action}
  </div>;
}

function EmptyState({ message }) {
  return <div className="empty-state"><CircleHelp size={22} /><p>{message}</p></div>;
}

function Dashboard({ data, loading, onNavigate }) {
  if (loading) return <PageLoading />;
  if (!data) return <EmptyState message="Dashboard data is unavailable." />;
  const { kpis, categories, suppliers, priorities } = data;
  const maxRisk = Math.max(...categories.map((item) => item.value_at_risk), 1);
  return <>
    <section className="hero-grid">
      <div className="hero-copy">
        <span className="eyebrow"><Sparkles size={14} /> Inventory intelligence, grounded in policy</span>
        <h1>Know what needs attention before it becomes a stock problem.</h1>
        <p>InventoryIQ joins operational signals, GPU-ranked anomaly detection, and policy-aware NVIDIA AI into one decisive workspace.</p>
        <div className="hero-actions">
          <button className="button primary" onClick={() => onNavigate("inventory")}><PackageSearch size={17} /> Investigate inventory</button>
          <button className="button secondary" onClick={() => onNavigate("policy")}><Bot size={17} /> Ask the policy</button>
        </div>
      </div>
      <div className="hero-signal">
        <div className="signal-header"><span>Exposure signal</span><Activity size={19} /></div>
        <div className="signal-value">{formatCurrency(kpis.total_slob_value_at_risk)}</div>
        <p>capital currently held in slow-moving or obsolete stock</p>
        <div className="signal-divider" />
        <div className="signal-stats"><span><b>{formatNumber(kpis.flagged_skus)}</b> flagged SKUs</span><span><b>{formatNumber(kpis.suppliers_with_drift)}</b> suppliers drifting</span></div>
      </div>
    </section>

    <section className="metric-grid">
      <Metric label="Total SKUs" value={formatNumber(kpis.total_skus)} subtext="live product catalogue" icon={Box} tone="lime" />
      <Metric label="Policy compliance" value={`${kpis.avg_compliance_score}%`} subtext="across all inventory" icon={ShieldCheck} tone="blue" />
      <Metric label="Below reorder point" value={formatNumber(kpis.skus_below_rop)} subtext="needs replenishment review" icon={ArrowDownRight} tone="amber" />
      <Metric label="Obsolete stock" value={formatNumber(kpis.obsolete_skus)} subtext="no movement in 90+ days" icon={AlertTriangle} tone="coral" />
    </section>

    <section className="dashboard-grid">
      <article className="panel risk-panel">
        <SectionHeader eyebrow="Risk landscape" title="Value at risk by category" detail="Where capital is getting stuck." />
        <div className="risk-bars">
          {categories.map((category) => <div className="bar-row" key={category.category}>
            <div className="bar-copy"><span>{category.category}</span><b>{formatCurrency(category.value_at_risk)}</b></div>
            <div className="bar-track"><i style={{ width: `${(category.value_at_risk / maxRisk) * 100}%` }} /></div>
            <small>{category.flagged} flagged · {category.compliance}% compliant</small>
          </div>)}
        </div>
      </article>
      <article className="panel nvidia-panel">
        <SectionHeader eyebrow="NVIDIA intelligence" title="Your AI operating layer" />
        <div className="nvidia-stack">
          <StackItem icon={Zap} title="RAPIDS cuML" detail="Ranks anomalous stock behaviour using GPU anomaly scores." />
          <StackItem icon={BrainCircuit} title="NeMo Retriever" detail="Finds relevant policy evidence before each answer." />
          <StackItem icon={Bot} title="NIM inference" detail="Turns policy and SKU data into concise next actions." />
        </div>
        <button className="text-button" onClick={() => onNavigate("policy")}>Open the policy copilot <ChevronRight size={16} /></button>
      </article>
    </section>

    <section className="panel priority-panel">
      <SectionHeader eyebrow="Priority queue" title="Decide on these next" detail="Highest-value inventory exceptions across the catalogue." action={<button className="text-button" onClick={() => onNavigate("inventory")}>See explorer <ChevronRight size={16} /></button>} />
      <div className="priority-list">
        {priorities.map((item) => <button className="priority-row" key={item.sku_id} onClick={() => onNavigate("inventory", item.sku_id)}>
          <span className={`severity ${getSeverity(item)}`} />
          <span className="priority-name"><b>{item.product_name}</b><small>{item.sku_id} · {item.category}</small></span>
          <span className="priority-action">{item.recommended_action}</span>
          <span className="priority-risk"><b>{formatCurrency(item.stock_value_at_risk)}</b><small>{item.slob_flag !== "NORMAL" ? item.slob_flag.replace("_", " ") : "Below ROP"}</small></span>
          <ChevronRight size={18} />
        </button>)}
      </div>
    </section>
  </>;
}

function StackItem({ icon: Icon, title, detail }) {
  return <div className="stack-item"><div className="stack-icon"><Icon size={18} /></div><div><b>{title}</b><p>{detail}</p></div></div>;
}

function Inventory({ initialSku, onClearInitial }) {
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState(null);
  const [insight, setInsight] = useState(null);
  const [thinking, setThinking] = useState(false);
  const path = `/api/inventory?search=${encodeURIComponent(search)}&category=${encodeURIComponent(category)}&status=${status}`;
  const { data, loading, error } = useApi(path, null);

  useEffect(() => {
    if (!initialSku) return;
    api(`/api/inventory/${initialSku}`).then((item) => { setSelected(item); onClearInitial(); }).catch(() => onClearInitial());
  }, [initialSku, onClearInitial]);

  async function requestInsight(mode) {
    if (!selected) return;
    setThinking(true); setInsight({ mode, answer: "" });
    try { const result = await api("/api/insights", { method: "POST", body: JSON.stringify({ sku_id: selected.sku_id, mode }) }); setInsight({ mode, answer: result.answer }); }
    catch (err) { setInsight({ mode, answer: err.message }); } finally { setThinking(false); }
  }

  return <>
    <SectionHeader eyebrow="Inventory explorer" title="Find the pressure points" detail="Search 500 SKUs, filter exceptions, then ask AI to explain the decision in context." />
    <section className="filter-bar">
      <label className="search-field"><Search size={17} /><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search SKU, item, or supplier" /></label>
      <label><span>Category</span><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="all">All categories</option>{data?.categories?.map((item) => <option key={item}>{item}</option>)}</select></label>
      <label><span>Focus</span><select value={status} onChange={(e) => setStatus(e.target.value)}><option value="all">All inventory</option><option value="below_rop">Below reorder point</option><option value="slob">SLOB watchlist</option><option value="obsolete">Obsolete only</option></select></label>
    </section>
    {error ? <EmptyState message={error} /> : <section className="explorer-layout">
      <article className="panel table-panel">
        <div className="table-caption"><span>{data?.items?.length || 0} items shown</span><span>Ranked by urgency and value at risk</span></div>
        {loading ? <PageLoading /> : <div className="table-wrap"><table><thead><tr><th>SKU / item</th><th>Health</th><th>Stock vs ROP</th><th>Lead-time drift</th><th>Value at risk</th><th /></tr></thead><tbody>
          {data?.items?.map((item) => <tr key={item.sku_id} className={selected?.sku_id === item.sku_id ? "selected-row" : ""} onClick={() => { setSelected(item); setInsight(null); }}>
            <td><b>{item.product_name}</b><small>{item.sku_id} · {item.category}</small></td>
            <td><HealthBadge item={item} /></td>
            <td><b>{formatNumber(item.current_stock)} <em>/ {formatNumber(item.policy_reorder_point)}</em></b><small>{item.current_stock < item.policy_reorder_point ? "Below policy ROP" : "Coverage intact"}</small></td>
            <td className={item.lead_time_drift_pct > 20 ? "bad-value" : ""}>{item.lead_time_drift_pct > 0 ? "+" : ""}{item.lead_time_drift_pct}%</td>
            <td>{formatCurrency(item.stock_value_at_risk)}</td><td><ChevronRight size={17} /></td>
          </tr>)}</tbody></table></div>}
      </article>
      <SkuDetail selected={selected} insight={insight} thinking={thinking} onInsight={requestInsight} onClose={() => setSelected(null)} />
    </section>}
  </>;
}

function HealthBadge({ item }) {
  const severity = getSeverity(item);
  const label = item.slob_flag !== "NORMAL" ? item.slob_flag.replace("_", " ") : item.current_stock < item.policy_reorder_point ? "REPLENISH" : "ON TRACK";
  return <span className={`health-badge ${severity}`}>{label}</span>;
}

function InsightNote({ answer, thinking }) {
  if (thinking) return <p className="thinking"><LoaderCircle size={16} /> Checking policy context...</p>;
  if (!answer) return null;
  return <details className="insight-note"><summary><Bot size={15} /> View AI policy note</summary><p>{answer}</p></details>;
}

function ReorderPointInsight({ item, answer, thinking }) {
  const dailyDemand = Number(item.avg_monthly_sales || 0) / 30;
  const leadDemand = Math.round(dailyDemand * Number(item.actual_lead_time_days || 0));
  const difference = Number(item.recommended_rop) - Number(item.policy_reorder_point);
  return <div className="insight-card rop-insight">
    <div className="insight-title"><BrainCircuit size={17} /> Reorder-point breakdown</div>
    <div className="formula-label">Daily demand × actual lead time + safety stock</div>
    <div className="formula-row"><div><span>{dailyDemand.toFixed(1)} units/day</span><small>Average demand</small></div><b>×</b><div><span>{item.actual_lead_time_days} days</span><small>Actual lead time</small></div><b>+</b><div><span>{formatNumber(item.safety_stock)}</span><small>Safety stock</small></div></div>
    <div className="formula-result"><span>Recommended reorder point</span><strong>{formatNumber(item.recommended_rop)} units</strong><small>{leadDemand} lead-time demand + {formatNumber(item.safety_stock)} safety stock</small></div>
    <div className={`insight-decision ${difference > 0 ? "risk" : ""}`}>{difference > 0 ? `Raise the policy ROP by ${formatNumber(difference)} units to reflect current lead time.` : difference < 0 ? `Current policy ROP is ${formatNumber(Math.abs(difference))} units above the calculated requirement.` : "Current policy ROP matches the calculated requirement."}</div>
    <p className="insight-explanation">{Number(item.actual_lead_time_days) > Number(item.policy_lead_time_days) ? `Supplier delivery is taking ${formatNumber(Number(item.actual_lead_time_days) - Number(item.policy_lead_time_days))} extra day${Number(item.actual_lead_time_days) - Number(item.policy_lead_time_days) === 1 ? "" : "s"}, so the reorder calculation uses the actual lead time to protect availability.` : `Delivery is in line with the policy lead-time assumption, so the calculation is driven by current demand and safety-stock coverage.`}</p>
    <InsightNote answer={answer} thinking={thinking} />
  </div>;
}

function ActionInsight({ item, answer, thinking }) {
  const obsolete = item.slob_flag === "OBSOLETE";
  const timeline = obsolete ? ["Confirm classification", "Calculate provision", "Start write-down, return, or disposal"] : ["Review the cause of low demand", "Choose promote, return, reposition, or hold", "Freeze replenishment without approval"];
  return <div className="insight-card action-insight">
    <div className="insight-title"><Sparkles size={17} /> Recommended action</div>
    <div className="action-highlight"><span>{item.slob_flag.replace("_", " ")}</span><strong>{item.recommended_action}</strong><small>{formatCurrency(item.stock_value_at_risk)} at risk · {item.days_since_movement} days since movement</small></div>
    <p className="insight-explanation">{obsolete ? `This item has had no movement for ${item.days_since_movement} days, which exceeds the 90-day obsolescence threshold. Stop replenishment and start the disposal or recovery process.` : `Average sales are below the policy threshold for a healthy SKU. Resolve the low-demand cause before raising another purchase order.`}</p>
    <ol className="action-steps">{timeline.map((step, index) => <li key={step}><b>{index + 1}</b><span>{step}</span></li>)}</ol>
    <InsightNote answer={answer} thinking={thinking} />
  </div>;
}

function SkuDetail({ selected, insight, thinking, onInsight, onClose }) {
  if (!selected) return <aside className="detail-panel empty-detail"><PackageSearch size={28} /><h3>Select an inventory item</h3><p>Its inventory position, policy gap, and AI recommendation will appear here.</p></aside>;
  const below = selected.current_stock < selected.policy_reorder_point;
  return <aside className="detail-panel">
    <div className="detail-heading"><div><span className="eyebrow">{selected.sku_id}</span><h3>{selected.product_name}</h3><p>{selected.category} · {selected.supplier_id}</p></div><button className="icon-button" onClick={onClose} title="Close detail"><X size={17} /></button></div>
    <HealthBadge item={selected} />
    <div className="detail-metrics"><div><span>Current stock</span><b>{formatNumber(selected.current_stock)}</b></div><div><span>Policy ROP</span><b>{formatNumber(selected.policy_reorder_point)}</b></div><div><span>Recommended ROP</span><b>{formatNumber(selected.recommended_rop)}</b></div><div><span>Compliance</span><b>{selected.compliance_score}%</b></div></div>
    <div className={`decision-callout ${below ? "risk" : ""}`}><Gauge size={17} /><p>{below ? `Stock is ${formatNumber(selected.policy_reorder_point - selected.current_stock)} units below the policy reorder point.` : "Current stock remains above the configured reorder point."}</p></div>
    <div className="ai-actions"><button className="button secondary" disabled={thinking} onClick={() => onInsight("rop")}><BrainCircuit size={16} /> Explain reorder point</button>{selected.slob_flag !== "NORMAL" && <button className="button secondary" disabled={thinking} onClick={() => onInsight("slob")}><Sparkles size={16} /> Recommend action</button>}</div>
    {insight?.mode === "rop" && <ReorderPointInsight item={selected} answer={insight.answer} thinking={thinking} />}
    {insight?.mode === "slob" && <ActionInsight item={selected} answer={insight.answer} thinking={thinking} />}
  </aside>;
}

function Suppliers({ data, loading }) {
  const [selected, setSelected] = useState(null);
  const items = data?.items || [];
  const maxDrift = Math.max(...items.map((item) => Math.abs(item.avg_drift_pct)), 1);
  return <>
    <SectionHeader eyebrow="Supplier pulse" title="Make lead-time drift visible" detail="See where actual supply performance is diverging from the policy assumptions that protect availability." />
    {loading ? <PageLoading /> : <section className="supplier-layout"><article className="panel supplier-chart"><div className="chart-head"><span>Average lead-time drift</span><span className="legend"><i /> within tolerance <i className="warning" /> SLA risk</span></div>{items.map((item) => <button className={`supplier-bar ${selected?.supplier_id === item.supplier_id ? "active" : ""}`} key={item.supplier_id} onClick={() => setSelected(item)}><span>{item.supplier_id}</span><div className="supplier-track"><i className={item.avg_drift_pct > 20 ? "warning" : ""} style={{ width: `${Math.abs(item.avg_drift_pct) / maxDrift * 100}%` }} /></div><b className={item.avg_drift_pct > 20 ? "bad-value" : ""}>{item.avg_drift_pct > 0 ? "+" : ""}{item.avg_drift_pct}%</b></button>)}</article><aside className="panel supplier-detail">{selected ? <><span className="eyebrow">Supplier operating profile</span><h2>{selected.supplier_id}</h2><div className="supplier-detail-grid"><div><span>Policy lead time</span><b>{selected.avg_policy_lead_time} days</b></div><div><span>Actual lead time</span><b>{selected.avg_actual_lead_time} days</b></div><div><span>SKUs covered</span><b>{selected.sku_count}</b></div><div><span>SLA breaches</span><b>{selected.breach_count}</b></div></div><div className="decision-callout risk"><AlertTriangle size={17} /><p>{selected.avg_drift_pct > 20 ? "Lead times are beyond the 20% tolerance. Escalate with this supplier before the next ordering cycle." : "Lead times are inside the policy tolerance. Continue monitoring the supplier trend."}</p></div></> : <div className="empty-detail"><Truck size={28} /><h3>Select a supplier</h3><p>Choose a supplier to compare actual delivery performance against the policy baseline.</p></div>}</aside></section>}
  </>;
}

function PolicyCopilot({ health }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([{ role: "assistant", content: "I’m ready to help you interpret the inventory policy. Ask about reorder points, supplier drift, slow movers, or service-level rules." }]);
  const [sending, setSending] = useState(false);
  const nimConfigured = health?.nim?.state === "ready" || health?.nim?.state === "configured";
  const samples = ["What is the reorder point formula?", "When should obsolete stock be written down?", "What action applies when supplier lead time drifts?", "How is compliance calculated?"];
  async function ask(value) {
    const prompt = value.trim(); if (!prompt || sending) return;
    setMessages((current) => [...current, { role: "user", content: prompt }]); setQuestion(""); setSending(true);
    try { const response = await api("/api/policy/ask", { method: "POST", body: JSON.stringify({ question: prompt }) }); setMessages((current) => [...current, { role: "assistant", content: response.answer, sources: response.sources }]); }
    catch (error) { setMessages((current) => [...current, { role: "assistant", content: error.message }]); } finally { setSending(false); }
  }
  return <>
    <SectionHeader eyebrow="Policy copilot" title="Ask the operational policy, not a generic chatbot" detail="NVIDIA NIM generates the answer after NeMo Retriever brings in the most relevant inventory policy context." />
    <section className="copilot-layout"><article className="panel chat-panel"><div className="chat-status"><div><span className={`status-dot ${health?.nim?.state || "offline"}`} /><b>{nimConfigured ? "NIM policy AI is configured" : "Offline fallback mode"}</b></div><span>Grounded in inventory_policy.txt</span></div><div className="messages">{messages.map((message, index) => <div key={index} className={`message ${message.role}`}><div className="message-avatar">{message.role === "assistant" ? <Bot size={17} /> : <span>YOU</span>}</div><div><p>{message.content}</p>{message.sources && <small><FileText size={13} /> {message.sources.join(", ")}</small>}</div></div>)}{sending && <div className="message assistant"><div className="message-avatar"><Bot size={17} /></div><p className="thinking"><LoaderCircle size={16} /> Retrieving policy context...</p></div>}</div><form className="composer" onSubmit={(event) => { event.preventDefault(); ask(question); }}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question about inventory policy..." rows="2" /><button className="button primary" type="submit" disabled={!question.trim() || sending} title="Send question"><Send size={17} /> Ask</button></form></article><aside className="panel prompt-panel"><span className="eyebrow">Start with a policy question</span><h3>Useful prompts</h3>{samples.map((sample) => <button key={sample} onClick={() => ask(sample)}>{sample}<ChevronRight size={16} /></button>)}<div className="copilot-note"><BrainCircuit size={18} /><p>Answers are based on the indexed policy source. The app keeps your NVIDIA API key on the server, never in the browser.</p></div></aside></section>
  </>;
}

function PageLoading() { return <div className="page-loading"><LoaderCircle size={22} /> Loading operational data...</div>; }

function App() {
  const [view, setView] = useState("dashboard");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [focusSku, setFocusSku] = useState(null);
  const healthState = useApi("/api/health", null);
  const dashboardState = useApi("/api/dashboard", null);
  const suppliersState = useApi("/api/suppliers", null);
  function navigate(nextView, sku = null) { setView(nextView); setFocusSku(sku); setMobileOpen(false); window.scrollTo({ top: 0, behavior: "smooth" }); }
  const activeItem = useMemo(() => navItems.find((item) => item.id === view), [view]);
  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? "open" : ""}`}>
      <div className="brand"><div className="brand-mark"><Box size={21} /></div><span>Inventory<span>IQ</span></span></div>
      <nav>{navItems.map(({ id, label, icon: Icon }) => <button className={view === id ? "nav-active" : ""} key={id} onClick={() => navigate(id)}><Icon size={18} /><span>{label}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="data-source"><Database size={16} /><div><b>Inventory database</b><span>500 SKUs online</span></div><Check size={15} /></div><p>AI inventory control<br />built on NVIDIA</p></div>
    </aside>
    {mobileOpen && <button className="backdrop" aria-label="Close menu" onClick={() => setMobileOpen(false)} />}
    <main>
      <header className="topbar"><button className="mobile-menu icon-button" onClick={() => setMobileOpen(true)} title="Open navigation"><Menu size={20} /></button><div className="breadcrumb"><span>Operations</span><ChevronRight size={14} /><b>{activeItem?.label}</b></div><div className="topbar-actions"><span className="last-sync"><span className="status-dot ready" /> Live operating view</span><button className="icon-button" onClick={() => { healthState.reload(); dashboardState.reload(); suppliersState.reload(); }} title="Refresh dashboard"><RefreshCw size={17} /></button></div></header>
      <div className="content"><StatusRail health={healthState.data} onRefresh={healthState.reload} />{healthState.error && <div className="inline-error">{healthState.error}</div>}<div className="page-content">{view === "dashboard" && <Dashboard data={dashboardState.data} loading={dashboardState.loading} onNavigate={navigate} />}{view === "inventory" && <Inventory initialSku={focusSku} onClearInitial={() => setFocusSku(null)} />}{view === "suppliers" && <Suppliers data={suppliersState.data} loading={suppliersState.loading} />}{view === "policy" && <PolicyCopilot health={healthState.data} />}</div></div>
    </main>
  </div>;
}

const rootElement = document.getElementById("root");
const root = window.__inventoryIQRoot || createRoot(rootElement);
window.__inventoryIQRoot = root;
root.render(<App />);
