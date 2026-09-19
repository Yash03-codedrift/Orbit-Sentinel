import React, { useState, useEffect } from "react";
import { motion } from "motion/react";
import { Shield, Target, Zap, Server, Activity, Database, Cpu, Rocket, ChevronDown, CheckCircle2, AlertTriangle, Layers, Github, Radio, Users, Timer } from "lucide-react";
import { useNavigate } from "react-router-dom";

const bg1 = "/assets/bg1.png";
const bg2 = "/assets/bg2.png";
const bg3 = "/assets/bg3.png";
const bg4 = "/assets/bg4.png";
const bg5 = "/assets/bg5.png";
const bgFooter = "/assets/bgFooter.png";

import type { Variants } from "motion/react";

// ─── Historical Validation Section ──────────────────────────────────────────
function HistoricalValidationSection() {
  const [loading, setLoading]   = useState(false);
  const [result,  setResult]    = useState<any>(null);
  const [error,   setError]     = useState<string|null>(null);

  const run = async () => {
    setLoading(true); setError(null); setResult(null);
    try {
      const res = await fetch("/api/history/iridium_cosmos");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult(await res.json());
    } catch (e: any) {
      setError(e.message || "Request failed");
    } finally { setLoading(false); }
  };

  const fmtPc = (v: number) => v < 0.001 ? v.toExponential(2) : v.toFixed(4);
  const riskColor = (r: string) =>
    r === "CRITICAL" ? "text-red-400" : r === "HIGH" ? "text-amber-400" : "text-emerald-400";

  return (
    <section className="py-24 relative overflow-hidden bg-[#03060e]">
      <div className="absolute inset-0 bg-gradient-to-b from-red-950/10 via-transparent to-transparent pointer-events-none" />
      <div className="relative max-w-5xl mx-auto px-6">

        {/* Header */}
        <motion.div initial={{opacity:0,y:24}} whileInView={{opacity:1,y:0}} transition={{duration:0.6}} viewport={{once:true}} className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-red-950/30 border border-red-800/30 text-red-400 text-xs font-mono px-3 py-1 rounded-full mb-4 uppercase tracking-widest">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse shrink-0" /> Historical Validation
          </div>
          <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4 text-white">
            FEBRUARY 10, 2009
          </h2>
          <p className="text-slate-300 max-w-2xl mx-auto leading-relaxed">
            Iridium-33 and Cosmos-2251 collided at 789 km altitude over Siberia at 11.7 km/s relative velocity —
            the first hypervelocity collision between two intact spacecraft. It created <strong className="text-red-400">2,200+ debris fragments</strong> still
            threatening ISS and Starlink today. <span className="text-white font-semibold">Nobody detected it in advance.</span>
          </p>
        </motion.div>

        {/* Run button */}
        {!result && (
          <div className="flex justify-center mb-10">
            <button
              onClick={run} disabled={loading}
              className="px-8 py-3.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white font-mono font-bold text-sm uppercase tracking-widest rounded-lg shadow-[0_0_30px_rgba(220,38,38,0.35)] hover:shadow-[0_0_40px_rgba(220,38,38,0.55)] transition-all active:scale-95 flex items-center gap-2"
            >
              {loading
                ? <><span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin shrink-0"/>RUNNING SIMULATION…</>
                : "▶ RUN HISTORICAL SIMULATION"}
            </button>
          </div>
        )}

        {error && (
          <div className="text-center text-red-400 font-mono text-sm mb-6 bg-red-950/20 border border-red-900/30 rounded p-3">
            Error: {error}
          </div>
        )}

        {/* Timeline */}
        {result && (
          <motion.div initial={{opacity:0,y:16}} animate={{opacity:1,y:0}} transition={{duration:0.5}} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(result.detection_timeline as any[]).map((t: any, i: number) => (
                <div key={i} className={`bg-slate-950/80 border rounded-lg p-4 font-mono ${
                  t.t_label.includes("ACTUAL") ? "border-red-600/60 shadow-[0_0_16px_rgba(220,38,38,0.2)]" : "border-slate-800/60"
                }`}>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] text-slate-500 uppercase tracking-widest">{t.t_label}</span>
                    <span className={`text-[10px] font-bold uppercase ${riskColor(t.risk_level)}`}>{t.risk_level}</span>
                  </div>
                  <div className="space-y-1 text-[11px]">
                    <div className="flex justify-between"><span className="text-slate-500">Miss distance</span><span className="text-white font-bold">{t.miss_distance_km} km</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Pc (Chan)</span><span className={`font-bold ${riskColor(t.risk_level)}`}>{fmtPc(t.collision_probability_chan)}</span></div>
                    <div className="flex justify-between"><span className="text-slate-500">Status</span>
                      <span className={t.detection_status==="DETECTED"?"text-amber-400 font-bold":"text-slate-400"}>{t.detection_status}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Maneuver recommendation */}
            {result.optimal_maneuver && (
              <div className="bg-emerald-950/20 border border-emerald-700/30 rounded-lg p-5 font-mono">
                <div className="text-xs text-emerald-400 font-bold uppercase tracking-widest mb-3 flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4"/> RL Agent Maneuver Recommendation @ {result.optimal_maneuver.burn_epoch_label}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
                  <div className="text-center"><div className="text-slate-500 text-[9px] uppercase mb-1">Delta-V</div><div className="text-white font-bold text-base">{result.optimal_maneuver.delta_v_ms} m/s</div></div>
                  <div className="text-center"><div className="text-slate-500 text-[9px] uppercase mb-1">Direction</div><div className="text-cyan-400 font-bold uppercase">{result.optimal_maneuver.direction.replace("_"," ")}</div></div>
                  <div className="text-center"><div className="text-slate-500 text-[9px] uppercase mb-1">Pre-burn miss</div><div className="text-red-400 font-bold">{result.optimal_maneuver.pre_maneuver_miss_km} km</div></div>
                  <div className="text-center"><div className="text-slate-500 text-[9px] uppercase mb-1">Post-burn miss</div><div className="text-emerald-400 font-bold text-base">{result.optimal_maneuver.post_maneuver_miss_km} km</div></div>
                </div>
              </div>
            )}

            {/* Conclusion */}
            <div className="text-center bg-slate-950/60 border border-cyan-900/30 rounded-lg p-6">
              <p className="text-slate-200 leading-relaxed text-sm font-mono">
                {result.conclusion}
              </p>
              <div className="mt-4 inline-flex items-center gap-2 bg-emerald-950/30 border border-emerald-700/30 px-4 py-2 rounded-full text-emerald-400 font-mono font-bold text-sm animate-pulse">
                ✓ COLLISION AVERTED — {result.debris_generated.toLocaleString()} DEBRIS FRAGMENTS PREVENTED
              </div>
            </div>

            <div className="text-center">
              <button onClick={()=>setResult(null)} className="text-[10px] font-mono text-slate-600 hover:text-slate-400 underline cursor-pointer">
                Reset simulation
              </button>
            </div>
          </motion.div>
        )}
      </div>
    </section>
  );
}


// Animation Variants
const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.6, ease: "easeOut" as const } }
};
const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  visible: { opacity: 1, transition: { staggerChildren: 0.1 } }
};

const NAV_LINKS = [
  { label: "Home", href: "#hero" },
  { label: "Sandbox", href: "#problem" },
  { label: "How It Works", href: "#solution" },
  { label: "Architecture", href: "#architecture" },
  { label: "Technology", href: "#technology" },
];

const SECTION_IDS = ["hero", "problem", "solution", "architecture", "technology"];

export default function LandingPage() {
  const navigate = useNavigate();
  const [activeSection, setActiveSection] = useState("hero");
  const [sandboxTab, setSandboxTab] = useState("density");
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const observers: IntersectionObserver[] = [];
    const lastId = SECTION_IDS[SECTION_IDS.length - 1];
    SECTION_IDS.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const config = id === lastId
        ? { threshold: 0.1, rootMargin: "-60px 0px 0px 0px" }
        : { threshold: 0.3, rootMargin: "-60px 0px -40% 0px" };
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveSection(id); },
        config
      );
      obs.observe(el);
      observers.push(obs);
    });
    const onScroll = () => {
      if (window.innerHeight + window.scrollY >= document.body.scrollHeight - 80) {
        setActiveSection(lastId);
      }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      observers.forEach((o) => o.disconnect());
      window.removeEventListener("scroll", onScroll);
    };
  }, []);

  const scrollTo = (href: string) => {
    const id = href.replace("#", "");
    if (id === "hero") window.scrollTo({ top: 0, behavior: "smooth" });
    else document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  };

  const handleLaunchDemo = () => {
    navigate("/app?demo=true");
  };

  return (
    <div className="min-h-screen bg-[#030611] text-white selection:bg-cyan-400/30" style={{ overflowY: "auto" }}>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-black/60 backdrop-blur-md border-b border-white/10">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <button onClick={() => scrollTo("#hero")} className="flex items-center gap-2 sm:gap-3">
            <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg border border-cyan-400/60 bg-cyan-400/10 flex items-center justify-center shrink-0">
              <Shield className="w-4 h-4 sm:w-5 sm:h-5 text-cyan-400" />
            </div>
            <div className="flex flex-col leading-tight">
              <span className="font-black text-sm sm:text-base tracking-tight">ORBIT<span className="text-cyan-400"> SENTINEL</span></span>
              <span className="hidden sm:block text-[9px] text-white/40 uppercase tracking-wider font-medium">Autonomous Orbital Collision Avoidance System</span>
            </div>
          </button>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-5 lg:gap-7 text-xs font-semibold tracking-widest uppercase">
            {NAV_LINKS.map(({ label, href }) => {
              const id = href.replace("#", "");
              const isActive = activeSection === id || (id === "hero" && activeSection === "hero");
              return (
                <button
                  key={href}
                  onClick={() => scrollTo(href)}
                  className={[
                    "relative transition-colors duration-200 pb-0.5",
                    isActive ? "text-cyan-400" : "text-white/60 hover:text-cyan-400",
                  ].join(" ")}
                >
                  {label}
                  {isActive && (
                    <motion.span
                      layoutId="nav-underline"
                      className="absolute -bottom-1 left-0 right-0 h-[2px] bg-cyan-400 rounded-full"
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Launch App button in nav */}
          <button
            onClick={handleLaunchDemo}
            className="hidden md:flex items-center gap-2 bg-cyan-400 hover:bg-cyan-300 text-black font-bold text-xs px-4 py-2 rounded transition-all"
          >
            <Rocket className="w-3.5 h-3.5" />
            LAUNCH APP
          </button>

          {/* Mobile hamburger */}
          <button
            className="md:hidden flex flex-col gap-1.5 p-2 text-white/70 hover:text-cyan-400 transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            <span className={`block w-5 h-0.5 bg-current transition-all duration-300 ${menuOpen ? "rotate-45 translate-y-2" : ""}`} />
            <span className={`block w-5 h-0.5 bg-current transition-all duration-300 ${menuOpen ? "opacity-0" : ""}`} />
            <span className={`block w-5 h-0.5 bg-current transition-all duration-300 ${menuOpen ? "-rotate-45 -translate-y-2" : ""}`} />
          </button>
        </div>

        {/* Mobile menu panel */}
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="md:hidden bg-black/95 backdrop-blur-md border-t border-white/10 px-4 py-4 flex flex-col gap-1"
          >
            {NAV_LINKS.map(({ label, href }) => {
              const id = href.replace("#", "");
              const isActive = activeSection === id;
              return (
                <button
                  key={href}
                  onClick={() => { scrollTo(href); setMenuOpen(false); }}
                  className={[
                    "text-left px-3 py-2.5 rounded text-xs font-semibold tracking-widest uppercase transition-colors",
                    isActive ? "bg-cyan-400/15 text-cyan-400" : "text-white/60 hover:text-white",
                  ].join(" ")}
                >
                  {label}
                </button>
              );
            })}
            <button
              onClick={handleLaunchDemo}
              className="mt-2 flex items-center justify-center gap-2 bg-cyan-400 hover:bg-cyan-300 text-black font-bold text-xs px-4 py-3 rounded transition-all"
            >
              <Rocket className="w-3.5 h-3.5" />
              LAUNCH APP
            </button>
          </motion.div>
        )}
      </nav>

      {/* ── HERO SECTION ── */}
      <section id="hero" className="relative min-h-[100dvh] flex flex-col overflow-hidden">

        {/* Full-bleed background image */}
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: `url(${bg1})` }} />
        <div className="absolute inset-0" style={{ background: "linear-gradient(to right, rgba(0,0,0,0.96) 0%, rgba(0,0,0,0.88) 30%, rgba(0,0,0,0.50) 58%, rgba(0,0,0,0.10) 100%)" }} />
        <div className="absolute bottom-0 left-0 right-0 h-28 bg-gradient-to-t from-[#030611] to-transparent" style={{ zIndex: 2 }} />

        {/* Main content */}
        <div className="relative flex-1 flex flex-col justify-center max-w-7xl mx-auto px-4 sm:px-6 w-full pt-24 pb-40 sm:pb-36" style={{ zIndex: 3 }}>
          <motion.div initial="hidden" animate="visible" variants={staggerContainer} className="max-w-xl">

            <motion.h1 variants={fadeInUp} className="font-black uppercase leading-none mb-4" style={{ fontSize: "clamp(3.5rem, 9vw, 7rem)", letterSpacing: "-0.03em" }}>
              <span className="text-white">ORBIT</span><span className="text-cyan-400"> SENTINEL</span>
            </motion.h1>

            <motion.p variants={fadeInUp} className="text-lg md:text-xl font-bold text-white uppercase tracking-wide leading-snug mb-6">
              Autonomous Orbital<br />Collision Avoidance<br />System
            </motion.p>

            <motion.div variants={fadeInUp} className="text-sm text-white/70 leading-relaxed mb-8 max-w-sm">
              <p>Earth's orbit has 23,000 tracked objects flying at 28,000 km/h. One collision cascade could render LEO unusable for centuries.</p>
              <p className="text-cyan-400 font-semibold mt-2">Orbit Sentinel is the bodyguard that never sleeps — and never checks Slack first.</p>
            </motion.div>

            {/* CTA Buttons */}
            <motion.div variants={fadeInUp} className="flex items-center gap-4">
              <button
                data-testid="btn-launch-demo"
                onClick={handleLaunchDemo}
                className="flex items-center gap-2 bg-cyan-400 hover:bg-cyan-300 text-black font-bold text-sm px-6 py-3 rounded transition-all"
              >
                <Rocket className="w-4 h-4" />
                LAUNCH DEMO
              </button>
              <button
                data-testid="btn-watch-video"
                className="flex items-center gap-2 border border-white/40 hover:border-white text-white font-semibold text-sm px-6 py-3 rounded transition-all"
                onClick={() => scrollTo("#problem")}
              >
                <span className="w-4 h-4 rounded-full border border-white/70 flex items-center justify-center">
                  <span className="w-0 h-0 border-t-[4px] border-t-transparent border-b-[4px] border-b-transparent border-l-[6px] border-l-white ml-0.5" />
                </span>
                WATCH VIDEO
              </button>
            </motion.div>
          </motion.div>
        </div>

        {/* Stats bar */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8, duration: 0.6 }}
          className="absolute bottom-8 sm:bottom-10 left-0 right-0"
          style={{ zIndex: 4 }}
        >
          <div className="max-w-7xl mx-auto px-3 sm:px-6">
            <div className="overflow-x-auto scrollbar-hide rounded-xl">
              <div className="bg-black/70 backdrop-blur-md border border-white/10 rounded-xl flex md:grid md:grid-cols-5 divide-x divide-white/10 min-w-max md:min-w-0">
                {[
                  { icon: <Radio className="w-4 h-4 sm:w-5 sm:h-5" />, value: "23,000+", label: "Tracked Objects", sub: "Actively monitored in LEO" },
                  { icon: <Zap className="w-4 h-4 sm:w-5 sm:h-5" />, value: "28,000 km/h", label: "Avg. Debris Speed", sub: "Relative velocity in orbit" },
                  { icon: <Target className="w-4 h-4 sm:w-5 sm:h-5" />, value: "500,000+", label: "Untracked (>1CM)", sub: "Dark objects in LEO" },
                  { icon: <Users className="w-4 h-4 sm:w-5 sm:h-5" />, value: "0", label: "Humans In Loop", sub: "Fully autonomous system" },
                  { icon: <Timer className="w-4 h-4 sm:w-5 sm:h-5" />, value: "<200ms", label: "Decision Latency", sub: "Detect → Decide → Act" },
                ].map((stat, i) => (
                  <div key={i} className="flex items-center gap-2 sm:gap-3 px-4 sm:px-5 py-3 sm:py-4 shrink-0 md:shrink">
                    <span className="text-cyan-400 opacity-80">{stat.icon}</span>
                    <div>
                      <div className="text-cyan-400 font-black font-mono text-base sm:text-lg leading-none">{stat.value}</div>
                      <div className="text-white text-[9px] sm:text-[10px] font-bold uppercase tracking-wide mt-0.5">{stat.label}</div>
                      <div className="text-white/40 text-[8px] sm:text-[9px] mt-0.5 hidden sm:block">{stat.sub}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Scroll to explore */}
        <motion.button
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 2, duration: 1 }}
          onClick={() => scrollTo("#problem")}
          className="absolute left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 text-white/40 hover:text-cyan-400 transition-colors cursor-pointer"
          style={{ zIndex: 6, bottom: "6px" }}
        >
          <span className="text-[9px] font-mono tracking-[0.25em] uppercase">Scroll to Explore</span>
          <ChevronDown className="w-4 h-4 animate-bounce" />
        </motion.button>
      </section>

      {/* Collision Sandbox Controller */}
      <section id="problem" className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-cover bg-top bg-no-repeat" style={{ backgroundImage: `url(${bg2})` }} />
        <div className="absolute inset-0 bg-black/80" />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true, margin: "-100px" }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeInUp} className="mb-12">
              <div className="inline-flex items-center gap-2 border border-cyan-400/30 bg-cyan-400/5 rounded px-3 py-1 text-[10px] font-mono text-cyan-400 mb-4 tracking-widest uppercase">
                <Zap className="w-3 h-3" /> Live Simulation Environment
              </div>
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">SYSTEM COLLISION SANDBOX CONTROLLER</h2>
              <p className="text-xl text-white/60 max-w-3xl">
                Simulate orbital conjunctions in real time. Inject debris events, trigger autonomous avoidance burns, and observe OrbitGuard's decision pipeline — all inside a controlled sandbox.
              </p>
            </motion.div>

            {/* Sandbox control panel */}
            <motion.div variants={fadeInUp} className="bg-black border border-white/10 rounded-xl overflow-hidden shadow-2xl shadow-cyan-400/10">
              {/* Title bar */}
              <div className="flex items-center justify-between bg-white/5 border-b border-white/10 px-5 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500" />
                  <div className="w-3 h-3 rounded-full bg-green-500" />
                </div>
                <span className="font-mono text-xs text-white/50 tracking-widest">SANDBOX — COLLISION_CONTROLLER_v2.1</span>
                <div className="flex items-center gap-1.5">
                  <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                  <span className="font-mono text-[10px] text-green-400">ACTIVE</span>
                </div>
              </div>

              {/* Tab bar */}
              <div className="flex overflow-x-auto border-b border-white/10 bg-white/3">
                {[
                  { id: "density", label: "Density Multiplier" },
                  { id: "velocity", label: "Velocity Compliance" },
                  { id: "bypass", label: "Bypass Margin" },
                  { id: "registry", label: "Satellite Registry" },
                  { id: "solar", label: "Solar Star Inbound" },
                  { id: "cascade", label: "Trigger Cascade" },
                  { id: "sgp4", label: "SGP4 Parallel Controller" },
                  { id: "hmac", label: "HMAC Command Interlock" },
                ].map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setSandboxTab(tab.id)}
                    className={[
                      "px-4 py-3 text-[10px] font-mono tracking-widest whitespace-nowrap border-r border-white/5 transition-all",
                      sandboxTab === tab.id
                        ? "bg-cyan-400/15 text-cyan-400 border-b-2 border-b-cyan-400"
                        : "text-white/40 hover:text-white/70",
                    ].join(" ")}
                  >
                    {tab.label.toUpperCase()}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              <div className="p-6">

                {/* DENSITY MULTIPLIER */}
                {sandboxTab === "density" && (
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">SATELLITE DENSITY</div>
                      <div className="space-y-4">
                        {[
                          { band: "LEO 400–600km", value: 78, count: "4,821 objects" },
                          { band: "LEO 600–800km", value: 92, count: "8,340 objects" },
                          { band: "LEO 800–1000km", value: 55, count: "3,190 objects" },
                          { band: "MEO 2000–20000km", value: 22, count: "1,200 objects" },
                        ].map((row, i) => (
                          <div key={i}>
                            <div className="flex justify-between text-[10px] font-mono mb-1">
                              <span className="text-white/60">{row.band}</span>
                              <span className="text-cyan-400">{row.count}</span>
                            </div>
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                              <div className="h-full bg-cyan-400 rounded-full transition-all" style={{ width: `${row.value}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">SPACE DEBRIS DENSITY</div>
                      <div className="space-y-4">
                        {[
                          { band: "Tracked >10cm", value: 60, count: "23,000 objects" },
                          { band: "Tracked 1–10cm", value: 85, count: "500,000 est." },
                          { band: "Untracked <1cm", value: 99, count: "128M+ est." },
                          { band: "Paint flecks / slag", value: 99, count: "Uncountable" },
                        ].map((row, i) => (
                          <div key={i}>
                            <div className="flex justify-between text-[10px] font-mono mb-1">
                              <span className="text-white/60">{row.band}</span>
                              <span className="text-red-400">{row.count}</span>
                            </div>
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                              <div className="h-full bg-red-500 rounded-full" style={{ width: `${row.value}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* VELOCITY COMPLIANCE */}
                {sandboxTab === "velocity" && (
                  <div>
                    <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">VELOCITY COMPLIANCE MATRIX</div>
                    <div className="overflow-x-auto">
                      <table className="w-full font-mono text-xs">
                        <thead>
                          <tr className="border-b border-white/10 text-white/40">
                            <th className="text-left pb-2 pr-4">Object ID</th>
                            <th className="text-left pb-2 pr-4">Orbital Band</th>
                            <th className="text-left pb-2 pr-4">Velocity (km/s)</th>
                            <th className="text-left pb-2 pr-4">Δv Budget</th>
                            <th className="text-left pb-2">Compliance</th>
                          </tr>
                        </thead>
                        <tbody>
                          {[
                            { id: "ISS-25544", band: "LEO 408km", vel: "7.66", dv: "0.8 m/s", status: "COMPLIANT" },
                            { id: "OBJ-4821", band: "LEO 820km", vel: "7.45", dv: "N/A", status: "DEBRIS" },
                            { id: "STARLNK-3821", band: "LEO 550km", vel: "7.61", dv: "2.1 m/s", status: "COMPLIANT" },
                            { id: "OBJ-8812", band: "LEO 860km", vel: "7.42", dv: "N/A", status: "DEBRIS" },
                            { id: "ASTRA-1N", band: "GEO 35786km", vel: "3.07", dv: "5.0 m/s", status: "COMPLIANT" },
                            { id: "OBJ-??", band: "LEO 835km", vel: "7.43", dv: "N/A", status: "UNTRACKED" },
                          ].map((row, i) => (
                            <tr key={i} className="border-b border-white/5">
                              <td className="py-2 pr-4 text-white/80">{row.id}</td>
                              <td className="py-2 pr-4 text-white/50">{row.band}</td>
                              <td className="py-2 pr-4 text-cyan-400">{row.vel}</td>
                              <td className="py-2 pr-4 text-white/60">{row.dv}</td>
                              <td className="py-2">
                                <span className={`px-2 py-0.5 rounded text-[9px] font-bold ${row.status === "COMPLIANT" ? "bg-green-500/20 text-green-400" : row.status === "DEBRIS" ? "bg-red-500/20 text-red-400" : "bg-yellow-500/20 text-yellow-400"}`}>{row.status}</span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* BYPASS MARGIN */}
                {sandboxTab === "bypass" && (
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">MANEUVER BYPASS THRESHOLDS</div>
                      <div className="space-y-4">
                        {[
                          { label: "Pc RED Alert Threshold", editable: "0.00100" },
                          { label: "Miss Distance Min (m)", editable: "1000" },
                          { label: "TCA Window (min)", editable: "60" },
                          { label: "Auto-Bypass Δv Limit", editable: "5.0" },
                          { label: "Override Authority", editable: "AUTONOMOUS" },
                        ].map((row, i) => (
                          <div key={i} className="flex items-center justify-between bg-white/5 border border-white/10 rounded px-3 py-2">
                            <span className="text-[10px] text-white/60 font-mono">{row.label}</span>
                            <span className="text-cyan-400 font-mono text-xs font-bold">{row.editable}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">SAFETY INTERLOCK STATUS</div>
                      <div className="space-y-3">
                        {[
                          { name: "Pre-burn validation", active: true },
                          { name: "Post-maneuver Pc re-check", active: true },
                          { name: "Secondary conjunction scan", active: true },
                          { name: "Fuel budget enforcement", active: true },
                          { name: "Human override port", active: false },
                        ].map((lock, i) => (
                          <div key={i} className="flex items-center justify-between">
                            <span className="font-mono text-[10px] text-white/60">{lock.name}</span>
                            <div className={`w-8 h-4 rounded-full flex items-center px-0.5 ${lock.active ? "bg-cyan-400/30" : "bg-white/10"}`}>
                              <div className={`w-3 h-3 rounded-full transition-all ${lock.active ? "bg-cyan-400 ml-auto" : "bg-white/30"}`} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* SATELLITE REGISTRY */}
                {sandboxTab === "registry" && (
                  <div>
                    <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">ACTIVE SATELLITE REGISTRY — 23,841 OBJECTS</div>
                    <div className="space-y-2">
                      {[
                        { norad: "25544", name: "ISS (ZARYA)", owner: "MULTI", inc: "51.6°", alt: "408km", type: "STATION" },
                        { norad: "48274", name: "STARLINK-2141", owner: "SPACEX", inc: "53.0°", alt: "550km", type: "COMMS" },
                        { norad: "04821", name: "COSMOS 1408 FRAG", owner: "ROSCOSMOS", inc: "82.5°", alt: "820km", type: "DEBRIS" },
                        { norad: "08812", name: "FENGYUN-1C DEB", owner: "CNSA", inc: "98.8°", alt: "860km", type: "DEBRIS" },
                        { norad: "39084", name: "TERRA", owner: "NASA", inc: "98.2°", alt: "705km", type: "EARTH-OBS" },
                        { norad: "?????", name: "UNKNOWN DARK OBJ", owner: "UNKNOWN", inc: "???", alt: "835km", type: "UNTRACKED" },
                      ].map((sat, i) => (
                        <div key={i} className="grid grid-cols-6 gap-2 font-mono text-[10px] bg-white/5 border border-white/10 rounded px-3 py-2">
                          <span className="text-white/40">{sat.norad}</span>
                          <span className="text-white col-span-2">{sat.name}</span>
                          <span className="text-white/50">{sat.inc}</span>
                          <span className="text-cyan-400">{sat.alt}</span>
                          <span className={`text-right font-bold ${sat.type === "DEBRIS" ? "text-red-400" : sat.type === "UNTRACKED" ? "text-yellow-400" : "text-green-400"}`}>{sat.type}</span>
                        </div>
                      ))}
                      <div className="text-center text-[9px] text-white/30 font-mono pt-2">↓ 23,835 more objects in registry</div>
                    </div>
                  </div>
                )}

                {/* SOLAR STAR INBOUND */}
                {sandboxTab === "solar" && (
                  <div className="grid md:grid-cols-3 gap-6">
                    <div className="md:col-span-2 space-y-4">
                      <div className="font-mono text-xs text-cyan-400 mb-2 tracking-widest">SOLAR EVENT MONITOR</div>
                      <div className="bg-yellow-500/10 border border-yellow-500/30 rounded p-4">
                        <div className="flex items-center gap-2 mb-3">
                          <Zap className="w-4 h-4 text-yellow-400" />
                          <span className="font-mono text-xs text-yellow-400 font-bold tracking-widest">X2.3 SOLAR FLARE — ACTIVE</span>
                        </div>
                        <div className="grid grid-cols-2 gap-3 font-mono text-xs">
                          <div><span className="text-white/40">Source:</span> <span className="text-white">AR3590</span></div>
                          <div><span className="text-white/40">Class:</span> <span className="text-yellow-400 font-bold">X2.3</span></div>
                          <div><span className="text-white/40">CME ETA:</span> <span className="text-white">T+38hrs</span></div>
                          <div><span className="text-white/40">Kp Index:</span> <span className="text-red-400 font-bold">7.4 (G3)</span></div>
                          <div><span className="text-white/40">Atm. Drag Δ:</span> <span className="text-red-400">+18% LEO</span></div>
                          <div><span className="text-white/40">TLE Epoch Age:</span> <span className="text-yellow-400">REFRESH REQ</span></div>
                        </div>
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">IMPACT ASSESSMENT</div>
                      <div className="space-y-3 text-[10px] font-mono">
                        {[
                          { item: "Orbital decay acceleration", level: "HIGH" },
                          { item: "TLE prediction accuracy", level: "DEGRADED" },
                          { item: "GPS signal integrity", level: "CAUTION" },
                          { item: "Conjunction Pc uncertainty", level: "ELEVATED" },
                          { item: "Uplink comms reliability", level: "NOMINAL" },
                        ].map((a, i) => (
                          <div key={i} className="flex justify-between items-center">
                            <span className="text-white/50">{a.item}</span>
                            <span className={`font-bold ${a.level === "HIGH" || a.level === "DEGRADED" ? "text-red-400" : a.level === "ELEVATED" || a.level === "CAUTION" ? "text-yellow-400" : "text-green-400"}`}>{a.level}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* TRIGGER CASCADE */}
                {sandboxTab === "cascade" && (
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">CASCADE TRIGGER CONTROLS</div>
                      <div className="space-y-3">
                        {[
                          { label: "Initial Collision Altitude", val: "820 km" },
                          { label: "Fragment Count (est.)", val: "2,400+" },
                          { label: "Cascade Velocity", val: "7.45 km/s" },
                          { label: "Spread Radius (72hr)", val: "±140 km" },
                          { label: "Secondary Collision Prob.", val: "68%" },
                        ].map((p, i) => (
                          <div key={i} className="flex justify-between bg-white/5 border border-white/10 rounded px-3 py-2">
                            <span className="font-mono text-[10px] text-white/60">{p.label}</span>
                            <span className="font-mono text-[10px] text-red-400 font-bold">{p.val}</span>
                          </div>
                        ))}
                        <button className="w-full mt-2 bg-red-500/20 border border-red-500/40 hover:bg-red-500/30 text-red-400 font-mono font-bold text-[10px] tracking-widest py-3 rounded transition-all flex items-center justify-center gap-2">
                          <AlertTriangle className="w-3 h-3" /> TRIGGER SIMULATED CASCADE
                        </button>
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">CASCADE PROPAGATION STAGES</div>
                      <div className="space-y-2">
                        {[
                          { stage: "01", event: "Initial Collision", status: "READY", color: "cyan-400" },
                          { stage: "02", event: "Fragment Cloud", status: "PENDING", color: "white/30" },
                          { stage: "03", event: "Secondary Impacts", status: "PENDING", color: "white/30" },
                          { stage: "04", event: "Network Cascade", status: "PENDING", color: "white/30" },
                          { stage: "05", event: "OrbitGuard Response", status: "ARMED", color: "green-400" },
                        ].map((s, i) => (
                          <div key={i} className="flex items-center gap-3 bg-white/5 border border-white/10 rounded px-3 py-2">
                            <span className="font-mono text-[10px] text-cyan-400">STAGE {s.stage}</span>
                            <span className="font-mono text-[10px] text-white/70 flex-1">{s.event}</span>
                            <span className={`font-mono text-[9px] font-bold ${s.status === "READY" ? "text-cyan-400" : s.status === "ARMED" ? "text-green-400" : "text-white/30"}`}>{s.status}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* SGP4 PARALLEL CONTROLLER */}
                {sandboxTab === "sgp4" && (
                  <div>
                    <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">SGP4 PARALLEL PROPAGATION WORKERS</div>
                    <div className="grid md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        {[
                          { id: "SGP4-W01", objects: 5800, load: 92, status: "RUNNING" },
                          { id: "SGP4-W02", objects: 5800, load: 88, status: "RUNNING" },
                          { id: "SGP4-W03", objects: 5800, load: 95, status: "RUNNING" },
                          { id: "SGP4-W04", objects: 5641, load: 74, status: "RUNNING" },
                          { id: "SGP4-W05", objects: 0, load: 0, status: "STANDBY" },
                        ].map((w, i) => (
                          <div key={i} className="bg-white/5 border border-white/10 rounded px-3 py-2">
                            <div className="flex justify-between items-center mb-1">
                              <span className="font-mono text-xs text-white/80">{w.id}</span>
                              <span className={`font-mono text-[9px] font-bold ${w.status === "RUNNING" ? "text-green-400" : "text-white/30"}`}>{w.status}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
                                <div className="h-full bg-cyan-400 rounded-full" style={{ width: `${w.load}%` }} />
                              </div>
                              <span className="font-mono text-[9px] text-white/40">{w.objects.toLocaleString()} obj</span>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div>
                        <div className="font-mono text-xs text-white/40 mb-3 tracking-widest">PROPAGATION METRICS</div>
                        <div className="space-y-3 font-mono text-xs">
                          {[
                            { label: "Cycle time", val: "0.98s" },
                            { label: "Objects/sec", val: "23,041" },
                            { label: "Propagation horizon", val: "72hrs" },
                            { label: "Epoch staleness", val: "0.4 days" },
                            { label: "k-d tree rebuild", val: "1Hz" },
                            { label: "Active conjunctions", val: "7 pairs" },
                          ].map((m, i) => (
                            <div key={i} className="flex justify-between border-b border-white/5 pb-2">
                              <span className="text-white/50">{m.label}</span>
                              <span className="text-cyan-400 font-bold">{m.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* HMAC COMMAND INTERLOCK */}
                {sandboxTab === "hmac" && (
                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">HMAC-SHA256 COMMAND AUTH</div>
                      <div className="space-y-3">
                        <div className="bg-green-500/10 border border-green-500/30 rounded p-3">
                          <div className="flex items-center gap-2 mb-2">
                            <Shield className="w-3 h-3 text-green-400" />
                            <span className="font-mono text-[10px] text-green-400 font-bold">INTERLOCK ARMED</span>
                          </div>
                          <div className="font-mono text-[9px] text-white/50 space-y-1">
                            <div>Algorithm: <span className="text-white">HMAC-SHA256</span></div>
                            <div>Key rotation: <span className="text-white">Every 6hrs</span></div>
                            <div>Nonce window: <span className="text-white">±30s</span></div>
                            <div>Last auth: <span className="text-green-400">T-4.2s ago</span></div>
                          </div>
                        </div>
                        <div>
                          <div className="font-mono text-[9px] text-white/30 mb-1">LAST SIGNED COMMAND DIGEST</div>
                          <div className="bg-black/50 border border-white/10 rounded px-3 py-2 font-mono text-[9px] text-cyan-400/80 break-all">
                            a3f9b2c7d1e04812...8f2a91bc34d06e55
                          </div>
                        </div>
                      </div>
                    </div>
                    <div>
                      <div className="font-mono text-xs text-cyan-400 mb-4 tracking-widest">COMMAND INTERLOCK LOG</div>
                      <div className="space-y-1.5">
                        {[
                          { cmd: "BURN_PROGRADE", auth: "PASS", time: "T-4s" },
                          { cmd: "TLE_REFRESH", auth: "PASS", time: "T-18s" },
                          { cmd: "SCAN_CONJUNCTIONS", auth: "PASS", time: "T-32s" },
                          { cmd: "OVERRIDE_REQUEST", auth: "REJECT", time: "T-1.2min" },
                          { cmd: "BURN_RETROGRADE", auth: "PASS", time: "T-8.4min" },
                        ].map((log, i) => (
                          <div key={i} className="flex justify-between bg-white/5 border border-white/10 rounded px-3 py-1.5 font-mono text-[9px]">
                            <span className="text-white/60">{log.cmd}</span>
                            <span className="text-white/30">{log.time}</span>
                            <span className={`font-bold ${log.auth === "PASS" ? "text-green-400" : "text-red-400"}`}>{log.auth}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

              </div>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Solution Overview */}
      <section id="solution" className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: `url(${bg3})` }} />
        <div className="absolute inset-0 bg-black/80" />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
            className="grid md:grid-cols-2 gap-12 items-center"
          >
            <motion.div variants={fadeInUp}>
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-6">DETERMINISTIC PHYSICS + AI REASONING</h2>
              <p className="text-lg text-white/60 mb-6">
                OrbitGuard fuses rigorous astrodynamics with cutting-edge LLM reasoning. It computes conjunction probabilities (Pc) using traditional SGP4 propagators, then hands the critical decision to an autonomous AI agent.
              </p>
              <ul className="space-y-4 font-mono text-sm">
                <li className="flex items-center gap-3"><CheckCircle2 className="text-cyan-400 w-5 h-5" /> FULLY AUTONOMOUS PIPELINE</li>
                <li className="flex items-center gap-3"><CheckCircle2 className="text-cyan-400 w-5 h-5" /> &lt;200MS DECISION LATENCY</li>
                <li className="flex items-center gap-3"><CheckCircle2 className="text-cyan-400 w-5 h-5" /> ZERO HUMAN APPROVAL DELAY</li>
              </ul>
            </motion.div>
            <motion.div variants={fadeInUp} className="bg-black border border-white/10 rounded-xl p-6 shadow-2xl shadow-cyan-400/10">
              <div className="flex items-center justify-between border-b border-white/10 pb-4 mb-4">
                <div className="flex gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
                <div className="font-mono text-xs text-white/50">orbitguard-agent-runtime</div>
              </div>
              <pre className="font-mono text-sm text-green-400 overflow-x-auto whitespace-pre-wrap">
{`> [SYS] Ingesting TLE epoch...
> [SYS] Propagating 23,000 objects...
> [WARN] Conjunction detected! Pc: 0.00312
> [AI] Evaluating avoidance vectors...
> [AI] Prograde +0.8m/s selected.
> [SYS] Executing burn...
> [SYS] Maneuver confirmed. Pc -> 0.00000`}
              </pre>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Historical Validation */}
      <HistoricalValidationSection />

      {/* System Architecture */}
      <section id="architecture" className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: `url(${bg4})` }} />
        <div className="absolute inset-0 bg-black/80" />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeInUp} className="mb-12">
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">SYSTEM ARCHITECTURE</h2>
              <p className="text-xl text-white/60 max-w-2xl">A 5-layer autonomous pipeline operating at machine speed.</p>
            </motion.div>

            <div className="space-y-6">
              {[
                { num: "01", title: "Sensor Ingestion", desc: "Radar, telescopes, LEO cross-tagging, TLE data, 1Hz refresh.", icon: <Activity className="w-6 h-6 text-cyan-400" /> },
                { num: "02", title: "State Vector Fusion", desc: "Kalman filter, 6D state vectors, 23,000 objects, uncertainty ellipsoids.", icon: <Database className="w-6 h-6 text-cyan-400" /> },
                { num: "03", title: "Conjunction Detection & Pc", desc: "k-d tree screening, SGP4, 72hr propagation, Foster/Alfano. Pc > 1/1000 = RED ALERT.", icon: <AlertTriangle className="w-6 h-6 text-red-400" /> },
                { num: "04", title: "AI Decision Agent", desc: "Groq llama-3.3-70b, burn direction, delta-v, validation against all 23k objects.", icon: <Cpu className="w-6 h-6 text-cyan-400" /> },
                { num: "05", title: "Command Execution", desc: "Encrypted uplink, post-maneuver verification, full loop < 60 seconds.", icon: <Rocket className="w-6 h-6 text-cyan-400" /> },
              ].map((layer, i) => (
                <motion.div key={i} variants={fadeInUp} className="flex gap-4 sm:gap-6 items-start bg-white/5 border border-white/5 p-4 sm:p-6 rounded-lg hover:border-cyan-400/50 transition-colors">
                  <div className="mt-1 shrink-0">{layer.icon}</div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2">
                      <span className="font-mono text-cyan-400 text-xs sm:text-sm">LAYER {layer.num}</span>
                      <h3 className="font-bold text-base sm:text-xl">{layer.title}</h3>
                    </div>
                    <p className="text-white/60 text-sm sm:text-base">{layer.desc}</p>
                  </div>
                </motion.div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* AI Components */}
      <section id="technology" className="py-24 relative overflow-hidden">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: `url(${bg5})` }} />
        <div className="absolute inset-0 bg-black/80" />
        <div className="relative z-10 max-w-7xl mx-auto px-6">
          <motion.div
            initial="hidden"
            whileInView="visible"
            viewport={{ once: true }}
            variants={staggerContainer}
          >
            <motion.div variants={fadeInUp} className="mb-12 text-center">
              <div className="inline-flex items-center gap-2 border border-cyan-400/40 bg-cyan-400/10 rounded-full px-4 py-1.5 text-[10px] font-mono text-cyan-400 tracking-widest uppercase mb-6">
                <Layers className="w-3 h-3" /> Orbital Physics Deep-Link Stacks
              </div>
              <h2 className="text-3xl md:text-5xl font-bold tracking-tight mb-4">Advanced Non-Linear Kepler Mechanics</h2>
              <p className="text-lg text-white/60 max-w-2xl mx-auto">
                Our auto-thruster networks execute orbital deflection paths immediately. We coordinate flight math on global secure aerospace pipelines.
              </p>
            </motion.div>

            <div className="grid md:grid-cols-3 gap-6 mb-12">
              <motion.div variants={fadeInUp} className="bg-black/60 border border-white/10 p-7 rounded-xl relative overflow-hidden flex flex-col gap-4">
                <div className="absolute top-0 right-0 w-28 h-28 bg-cyan-400/10 rounded-full blur-3xl pointer-events-none" />
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-bold text-lg leading-snug uppercase tracking-wide">SGP4 Parallel Propagator</h3>
                  <Database className="w-6 h-6 text-cyan-400 shrink-0 mt-0.5" />
                </div>
                <p className="text-sm text-white/60 leading-relaxed flex-1">
                  Parses live NORAD geodetic feeds and calculates Keplerian elements to ±12 meters relative accuracy, compiling thousands of trajectory updates in parallel.
                </p>
                <div className="font-mono text-[10px] text-cyan-400 tracking-widest uppercase border-t border-white/10 pt-4">
                  Rust Descent Assembly &nbsp;·&nbsp; 0.04ms Solver Latency
                </div>
              </motion.div>

              <motion.div variants={fadeInUp} className="bg-black/60 border border-white/10 p-7 rounded-xl relative overflow-hidden flex flex-col gap-4">
                <div className="absolute top-0 right-0 w-28 h-28 bg-cyan-400/10 rounded-full blur-3xl pointer-events-none" />
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-bold text-lg leading-snug uppercase tracking-wide">HMAC Command Interlock</h3>
                  <Shield className="w-6 h-6 text-cyan-400 shrink-0 mt-0.5" />
                </div>
                <p className="text-sm text-white/60 leading-relaxed flex-1">
                  Aegis-tier command verification prevents malicious delta-v commands. Burn trajectories require dual signature authorization codes matching secure network keys.
                </p>
                <div className="font-mono text-[10px] text-cyan-400 tracking-widest uppercase border-t border-white/10 pt-4">
                  Secure Verify System &nbsp;·&nbsp; Dual Key Handshake
                </div>
              </motion.div>

              <motion.div variants={fadeInUp} className="bg-black/60 border border-white/10 p-7 rounded-xl relative overflow-hidden flex flex-col gap-4">
                <div className="absolute top-0 right-0 w-28 h-28 bg-yellow-500/10 rounded-full blur-3xl pointer-events-none" />
                <div className="flex items-start justify-between gap-3">
                  <h3 className="font-bold text-lg leading-snug uppercase tracking-wide">Agentic MARL Decisions</h3>
                  <Cpu className="w-6 h-6 text-yellow-400 shrink-0 mt-0.5" />
                </div>
                <p className="text-sm text-white/60 leading-relaxed flex-1">
                  Leverages Multi-Agent Reinforcement Learning (MARL) algorithms. Updates satellite propulsion thrusters dynamically to maximize miss distance margins in seconds.
                </p>
                <div className="font-mono text-[10px] text-yellow-400 tracking-widest uppercase border-t border-white/10 pt-4">
                  Decentralized PPO Decision Pipeline
                </div>
              </motion.div>
            </div>

            <motion.div variants={fadeInUp} className="bg-[#0a0a0a] border border-red-500/30 rounded-xl overflow-hidden shadow-[0_0_30px_rgba(255,0,0,0.1)]">
              <div className="bg-red-500/10 border-b border-red-500/20 px-4 py-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-500" />
                <span className="font-mono text-xs text-red-500 tracking-widest font-bold">LIVE INTERCEPT: MISSION_LOG_0X9A</span>
              </div>
              <div className="p-6 font-mono text-sm leading-relaxed">
                <div className="text-red-500 font-bold mb-2">Conjunction Alert: Object #4821 (Cosmos 1408 fragment) x ISS Orbital Band</div>
                <div className="text-white/50 mb-6">Pc: 0.00312 | TCA: T-47 min | Miss distance: 180m | Relative velocity: 14.2 km/s</div>

                <div className="text-blue-400 mb-6 pl-4 border-l-2 border-blue-500/30">
                  [REASONING]<br/>
                  Analysis indicates target object is within the critical uncertainty threshold (Pc &gt; 1/1000).
                  A prograde maneuver is prioritized over retrograde to minimize intersection time while avoiding
                  secondary conjunctions with object #8812 trailing in the +10km band. Required delta-v
                  calculated at 0.8 m/s to achieve safe miss distance &gt; 4km.
                </div>

                <div className="text-green-500 font-bold bg-green-500/10 inline-block px-3 py-1 rounded">
                  Decision: PROGRADE BURN 0.8 m/s at T-42 min — EXECUTED AUTONOMOUSLY
                </div>
              </div>
            </motion.div>

            {/* Final CTA section */}
            <motion.div variants={fadeInUp} className="mt-16 text-center">
              <h3 className="text-2xl md:text-4xl font-bold tracking-tight mb-4">Ready to see it in action?</h3>
              <p className="text-white/60 mb-8 max-w-xl mx-auto">Launch the live dashboard to monitor real-time conjunction events, trigger maneuver burns, and watch the AI agent protect orbital assets autonomously.</p>
              <button
                onClick={handleLaunchDemo}
                className="inline-flex items-center gap-3 bg-cyan-400 hover:bg-cyan-300 text-black font-black text-base px-8 py-4 rounded-lg transition-all shadow-[0_0_30px_rgba(34,211,238,0.3)] hover:shadow-[0_0_40px_rgba(34,211,238,0.5)]"
              >
                <Rocket className="w-5 h-5" />
                LAUNCH ORBIT SENTINEL DEMO
              </button>
            </motion.div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative overflow-hidden border-t border-white/10">
        <div className="absolute inset-0 bg-cover bg-center bg-no-repeat" style={{ backgroundImage: `url(${bgFooter})` }} />
        <div className="absolute inset-0 bg-black/88" />

        <div className="relative z-10 max-w-7xl mx-auto px-6 pt-16 pb-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-8 md:gap-10 mb-12 border-b border-white/10 pb-12">
            <div className="md:col-span-1">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg border border-cyan-400/60 bg-cyan-400/10 flex items-center justify-center">
                  <Shield className="w-5 h-5 text-cyan-400" />
                </div>
                <span className="font-black text-xl tracking-tight">ORBIT<span className="text-cyan-400"> SENTINEL</span></span>
              </div>
              <p className="text-xs text-white/40 leading-relaxed font-mono">
                Autonomous Orbital Collision Avoidance System. Zero humans in the loop. Always on guard.
              </p>
            </div>

            <div>
              <div className="font-mono text-[10px] text-cyan-400 tracking-widest uppercase mb-4">System</div>
              <ul className="space-y-2 text-xs text-white/50">
                {[
                  { label: "How It Works", href: "#solution" },
                  { label: "System Architecture", href: "#architecture" },
                  { label: "Sandbox Controller", href: "#problem" },
                  { label: "SGP4 Propagator", href: "#technology" },
                  { label: "HMAC Interlock", href: "#technology" },
                ].map(({ label, href }) => (
                  <li key={label}><button onClick={() => scrollTo(href)} className="hover:text-cyan-400 transition-colors text-left">{label}</button></li>
                ))}
              </ul>
            </div>

            <div>
              <div className="font-mono text-[10px] text-cyan-400 tracking-widest uppercase mb-4">Technology</div>
              <ul className="space-y-2 text-xs text-white/50">
                {["Kepler Mechanics Engine", "MARL Decision Pipeline", "Conjunction Detection", "Delta-V Optimiser", "TLE Epoch Processing"].map(l => (
                  <li key={l}><span className="hover:text-cyan-400 transition-colors cursor-default">{l}</span></li>
                ))}
              </ul>
            </div>

            <div>
              <div className="font-mono text-[10px] text-cyan-400 tracking-widest uppercase mb-4">Mission Stats</div>
              <div className="space-y-3">
                {[
                  { val: "23,000+", label: "Objects Tracked" },
                  { val: "0", label: "Humans In Loop" },
                  { val: "<200ms", label: "Decision Latency" },
                  { val: "∞", label: "Uptime Target" },
                ].map(s => (
                  <div key={s.label} className="flex justify-between text-xs border-b border-white/5 pb-2">
                    <span className="text-white/50">{s.label}</span>
                    <span className="text-cyan-400 font-mono font-bold">{s.val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="flex flex-col md:flex-row items-center justify-between gap-4 text-[10px] font-mono text-white/30">
            <div className="flex items-center gap-4">
              <span>&copy; {new Date().getFullYear()} Orbit Sentinel. All rights reserved.</span>
              <span className="text-white/15">·</span>
              <span>Space &amp; Aerospace · Agentic &amp; Autonomous Systems</span>
            </div>
            <div className="flex items-center gap-6">
              <span className="hover:text-white/60 cursor-pointer transition-colors">Privacy Policy</span>
              <span className="hover:text-white/60 cursor-pointer transition-colors">Terms of Use</span>
              <span className="text-white/15">·</span>
              <span className="text-cyan-400/60">Built for FAR AWAY 2026 Hackathon</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
