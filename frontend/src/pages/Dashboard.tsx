import { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import {
    Activity, AlertTriangle, CheckCircle, Play, Eye, Clock,
    ShieldAlert, Flame, Network, ClipboardList, Radar,
} from 'lucide-react';
import api from '../api/axios';
import { useSSE } from '../context/SSEContext';
import ScrollText from '../components/ScrollText';
import { status, severity } from '../theme/palette';

const riskColor = (score: number | null) => {
    if (score == null) return 'text-gray-400';
    if (score >= 85) return 'text-red-600 dark:text-red-400';
    if (score >= 70) return 'text-orange-600 dark:text-orange-400';
    if (score >= 50) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-blue-600 dark:text-blue-400';
};

const relTime = (d: string) => {
    const diff = Date.now() - new Date(d).getTime();
    const s = Math.floor(diff / 1000);
    if (s < 60) return `${Math.max(0, s)}s ago`;
    const m = Math.floor(s / 60); if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60); if (h < 24) return `${h}h ago`;
    return `${Math.floor(h / 24)}d ago`;
};

const ASSET_LABEL: Record<string, string> = {
    domain: 'Domains', subdomain: 'Subdomains', ip: 'IPs', url: 'URLs', service: 'Services',
};
const REM_LABEL: Record<string, string> = {
    todo: 'To Do', in_progress: 'In Progress', blocked: 'Blocked', done: 'Done', wont_fix: "Won't Fix",
};

// Compact posture readout cell used in the radar hero.
const PostureCell = ({ icon: Icon, label, value, accent }: any) => (
    <div className="bg-gray-50 dark:bg-gray-800/40 rounded-lg border border-gray-200 dark:border-gray-800 p-3">
        <div className="flex items-center justify-between">
            <span className="text-[11px] uppercase tracking-wide text-gray-500">{label}</span>
            <Icon className={`w-3.5 h-3.5 ${accent}`} />
        </div>
        <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">{value}</div>
    </div>
);

const Dashboard = () => {
    const navigate = useNavigate();
    const viewPath = (scan: any) =>
        scan.mode === 'agentic' && scan.objective ? `/ai-scan/${scan.id}` : `/scan/${scan.id}`;
    const { addEventListener, removeEventListener } = useSSE();

    const [loading, setLoading] = useState(true);
    const [scanCounts, setScanCounts] = useState({ total: 0, running: 0, completed: 0, failed: 0 });
    const [recentScans, setRecentScans] = useState<any[]>([]);
    const [trendData, setTrendData] = useState<any[]>([]);
    const [vulnDist, setVulnDist] = useState<any>({ Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 });
    const [exposure, setExposure] = useState<any>(null);
    const [assets, setAssets] = useState<any>(null);
    const [remStats, setRemStats] = useState<any>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    // Measured width of the scan-activity chart so its SVG fills the (full-width) panel.
    const chartWrapRef = useRef<HTMLDivElement>(null);
    const [chartW, setChartW] = useState(760);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [statsRes, expRes, assetRes, remRes] = await Promise.all([
                    api.get('/scans/dashboard-stats'),
                    api.get('/ctem/exposures/summary').catch(() => null),
                    api.get('/ctem/assets/summary').catch(() => null),
                    api.get('/ctem/remediations').catch(() => null),
                ]);

                const data = statsRes?.data;
                if (data && data.totalScans) {
                    setScanCounts({
                        total: data.totalScans.value, running: data.runningScans.value,
                        completed: data.completedScans.value, failed: data.failedScans.value,
                    });
                    setTrendData(data.chartData || []);
                    setVulnDist(data.vulnDist || { Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 });
                    setRecentScans((data.recentScans || []).map((s: any) => ({
                        ...s,
                        findings: {
                            Critical: s.critical_count || 0, High: s.high_count || 0,
                            Medium: s.medium_count || 0, Low: s.low_count || 0,
                        },
                    })));
                }
                if (expRes?.data) setExposure(expRes.data);
                if (assetRes?.data) setAssets(assetRes.data);
                if (remRes?.data) {
                    const rems: any[] = Array.isArray(remRes.data) ? remRes.data : [];
                    const byStatus: Record<string, number> = {};
                    rems.forEach((r) => { byStatus[r.status] = (byStatus[r.status] || 0) + 1; });
                    setRemStats({
                        total: rems.length,
                        open: rems.filter((r) => !['done', 'wont_fix'].includes(r.status)).length,
                        breached: rems.filter((r) => r.slaBreached).length,
                        byStatus,
                    });
                }
                setLastUpdated(new Date());
            } catch (error) {
                console.error('Failed to fetch dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
        const onScanUpdate = () => fetchData();
        addEventListener('SCAN_UPDATE', onScanUpdate);
        return () => removeEventListener('SCAN_UPDATE', onScanUpdate);
    }, []);

    useEffect(() => {
        const el = chartWrapRef.current;
        if (!el) return;
        const update = () => setChartW(el.clientWidth || 760);
        update();
        const ro = new ResizeObserver(update);
        ro.observe(el);
        return () => ro.disconnect();
    }, [loading]);

    // Severity distribution (open exposures) drives the radar; fall back to legacy aggregate.
    const sevSrc = exposure?.bySeverity || vulnDist;
    const sevDist = {
        Critical: sevSrc.Critical || 0, High: sevSrc.High || 0,
        Medium: sevSrc.Medium || 0, Low: sevSrc.Low || 0,
    };
    const avgRisk = exposure?.avgRiskScore ?? 0;
    const highPriority = sevDist.Critical + sevDist.High;

    // ---- Threat Radar: a spider chart of severity counts + a rotating radar sweep ----
    const ThreatRadar = () => {
        const size = 240, cc = size / 2, maxR = 92;
        const axes = [
            { key: 'Critical', short: 'CRIT', count: sevDist.Critical, color: severity.critical, angle: -90 },
            { key: 'High', short: 'HIGH', count: sevDist.High, color: severity.high, angle: 0 },
            { key: 'Medium', short: 'MED', count: sevDist.Medium, color: severity.medium, angle: 90 },
            { key: 'Low', short: 'LOW', count: sevDist.Low, color: severity.low, angle: 180 },
        ];
        const max = Math.max(...axes.map((a) => a.count), 1);
        const pt = (deg: number, r: number): [number, number] => {
            const a = (deg * Math.PI) / 180;
            return [cc + r * Math.cos(a), cc + r * Math.sin(a)];
        };
        const poly = axes.map((a) => pt(a.angle, (a.count / max) * maxR).join(',')).join(' ');
        const wedgeEnd = pt(-90 + 55, maxR);

        return (
            <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[260px] mx-auto">
                <defs>
                    <radialGradient id="radarSweep" cx="50%" cy="50%" r="50%">
                        <stop offset="0%" stopColor={status.info} stopOpacity="0.45" />
                        <stop offset="100%" stopColor={status.info} stopOpacity="0" />
                    </radialGradient>
                </defs>

                {/* scale rings */}
                {[0.25, 0.5, 0.75, 1].map((f) => (
                    <circle key={f} cx={cc} cy={cc} r={maxR * f} fill="none"
                        className="stroke-gray-200 dark:stroke-gray-700/60" strokeWidth="1" />
                ))}
                {/* spokes */}
                {axes.map((a) => { const [x, y] = pt(a.angle, maxR); return (
                    <line key={a.key} x1={cc} y1={cc} x2={x} y2={y}
                        className="stroke-gray-200 dark:stroke-gray-700/60" strokeWidth="1" />
                ); })}

                {/* rotating radar sweep */}
                <path d={`M ${cc} ${cc} L ${cc} ${cc - maxR} A ${maxR} ${maxR} 0 0 1 ${wedgeEnd[0]} ${wedgeEnd[1]} Z`}
                    fill="url(#radarSweep)">
                    <animateTransform attributeName="transform" type="rotate"
                        from={`0 ${cc} ${cc}`} to={`360 ${cc} ${cc}`} dur="6s" repeatCount="indefinite" />
                </path>

                {/* data polygon */}
                <polygon points={poly} fill={status.info} fillOpacity="0.18" stroke={status.info} strokeWidth="2" strokeLinejoin="round" className="transition-all duration-700" />

                {/* vertices + axis labels */}
                {axes.map((a) => {
                    const [x, y] = pt(a.angle, (a.count / max) * maxR);
                    const [lx, ly] = pt(a.angle, maxR + 14);
                    return (
                        <g key={a.key}>
                            {a.count > 0 && <circle cx={x} cy={y} r="4" fill={a.color} stroke="#fff" strokeWidth="1.5" />}
                            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" className="fill-gray-400 dark:fill-gray-500 text-[8px] font-semibold">{a.short}</text>
                        </g>
                    );
                })}
                <circle cx={cc} cy={cc} r="2.5" className="fill-gray-400 dark:fill-gray-500" />
            </svg>
        );
    };

    // ---- Scan-activity line chart (Total vs Completed) ----
    const LineChart = () => {
        const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
        const height = 220, width = Math.max(320, chartW), padding = 28;
        if (!trendData.length) return <div className="flex items-center justify-center h-full text-sm text-gray-500">No activity yet.</div>;
        const maxVal = Math.max(...trendData.map((d) => d.total), 5);
        const getX = (i: number) => (i / Math.max(1, trendData.length - 1)) * (width - 2 * padding) + padding;
        const getY = (val: number) => height - padding - (val / maxVal) * (height - 2 * padding);
        const pointsTotal = trendData.map((d, i) => `${getX(i)},${getY(d.total)}`).join(' ');
        const pointsCompleted = trendData.map((d, i) => `${getX(i)},${getY(d.completed)}`).join(' ');

        return (
            <div className="w-full h-full relative">
                <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-visible">
                    {[0, 0.25, 0.5, 0.75, 1].map((p) => (
                        <line key={p} x1={padding} y1={height - padding - p * (height - 2 * padding)}
                            x2={width - padding} y2={height - padding - p * (height - 2 * padding)}
                            className="stroke-gray-200 dark:stroke-gray-700" strokeDasharray="4 4" strokeWidth="1" />
                    ))}
                    <polyline points={pointsTotal} fill="none" stroke={status.info} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                    <polyline points={pointsCompleted} fill="none" stroke={status.success} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                    {hoveredIndex !== null && (
                        <line x1={getX(hoveredIndex)} y1={padding} x2={getX(hoveredIndex)} y2={height - padding}
                            className="stroke-gray-400 dark:stroke-gray-600" strokeWidth="1" strokeDasharray="4 4" />
                    )}
                    {trendData.map((d, i) => {
                        const x = getX(i), isHovered = hoveredIndex === i;
                        return (
                            <g key={i}>
                                <circle cx={x} cy={getY(d.total)} r={isHovered ? '6' : '4'} fill={status.info} stroke="#fff" strokeWidth="2" className="transition-all duration-200" />
                                <circle cx={x} cy={getY(d.completed)} r={isHovered ? '6' : '4'} fill={status.success} stroke="#fff" strokeWidth="2" className="transition-all duration-200" />
                                <text x={x} y={height - 6} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[10px]">{d.date}</text>
                            </g>
                        );
                    })}
                    {trendData.map((_, i) => (
                        <rect key={i} x={getX(i) - (width / trendData.length / 2)} y={0}
                            width={width / trendData.length} height={height} fill="transparent"
                            onMouseEnter={() => setHoveredIndex(i)} onMouseLeave={() => setHoveredIndex(null)} className="cursor-crosshair" />
                    ))}
                </svg>
                {hoveredIndex !== null && (
                    <div className="absolute bg-gray-800 border border-gray-700 p-3 rounded-lg shadow-xl z-10 pointer-events-none"
                        style={{ left: `${(hoveredIndex / Math.max(1, trendData.length - 1)) * 100}%`, top: '6%', transform: 'translateX(-50%)' }}>
                        <p className="text-white font-bold text-sm mb-2">{trendData[hoveredIndex].date}</p>
                        <div className="space-y-1 text-xs">
                            <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-blue-500" /><span className="text-gray-400">Total:</span><span className="text-white font-mono ml-auto">{trendData[hoveredIndex].total}</span></div>
                            <div className="flex items-center gap-2"><div className="w-2 h-2 rounded-full bg-green-500" /><span className="text-gray-400">Completed:</span><span className="text-white font-mono ml-auto">{trendData[hoveredIndex].completed}</span></div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    if (loading) return <div className="flex justify-center items-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500" /></div>;

    const sevTotal = sevDist.Critical + sevDist.High + sevDist.Medium + sevDist.Low;
    const assetMaxType = Math.max(1, ...Object.values(assets?.byType || {}).map((v) => Number(v)));

    return (
        <PageTransition className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Security Dashboard</h1>
                    <p className="text-sm text-gray-500">Last updated: {lastUpdated ? lastUpdated.toLocaleTimeString() : '—'}</p>
                </div>
                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={() => navigate('/scan/new')}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors shadow-lg shadow-blue-500/20">
                    <Play className="w-4 h-4" /> Start a New Scan
                </motion.button>
            </div>

            {/* Threat Radar hero */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Radar className="w-5 h-5 text-blue-500" />
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white">Threat Radar</h3>
                    <span className="ml-2 inline-flex items-center gap-1.5 text-xs text-gray-500"><span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" /> live</span>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-center">
                    {/* Radar + severity legend */}
                    <div>
                        <ThreatRadar />
                        <div className="flex flex-wrap justify-center gap-x-5 gap-y-2 mt-4">
                            {[
                                { label: 'Critical', count: sevDist.Critical, dot: 'bg-red-500' },
                                { label: 'High', count: sevDist.High, dot: 'bg-orange-500' },
                                { label: 'Medium', count: sevDist.Medium, dot: 'bg-yellow-500' },
                                { label: 'Low', count: sevDist.Low, dot: 'bg-blue-500' },
                            ].map((s) => (
                                <span key={s.label} className="inline-flex items-center gap-2 text-sm">
                                    <span className={`w-2.5 h-2.5 rounded-full ${s.dot}`} />
                                    <span className="text-gray-600 dark:text-gray-300">{s.label}</span>
                                    <span className="font-mono font-semibold text-gray-900 dark:text-white">{s.count}</span>
                                </span>
                            ))}
                        </div>
                    </div>

                    {/* Posture readouts */}
                    <div className="space-y-4">
                        <div className="bg-gray-50 dark:bg-gray-800/40 rounded-xl border border-gray-200 dark:border-gray-800 p-4 flex items-center justify-between">
                            <div>
                                <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">Risk Score</p>
                                <div className="flex items-baseline gap-1">
                                    <span className={`text-4xl font-bold ${riskColor(avgRisk)}`}>{avgRisk}</span>
                                    <span className="text-sm text-gray-500">/100</span>
                                </div>
                            </div>
                            <div className="text-right">
                                <p className="text-xs uppercase tracking-wide text-gray-500 mb-1">High Priority</p>
                                <span className={`text-2xl font-bold ${highPriority > 0 ? 'text-orange-500' : 'text-gray-400'}`}>{highPriority}</span>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <PostureCell icon={ShieldAlert} label="Open Exposures" value={exposure?.totalOpen ?? sevTotal} accent="text-blue-500" />
                            <PostureCell icon={Flame} label="Known-Exploited" value={exposure?.kevCount ?? 0} accent="text-red-500" />
                            <PostureCell icon={AlertTriangle} label="Overdue" value={exposure?.overdueCount ?? 0} accent="text-red-500" />
                            <PostureCell icon={Clock} label="Due ≤ 7d" value={exposure?.dueSoonCount ?? 0} accent="text-orange-500" />
                        </div>
                    </div>
                </div>
            </div>

            {/* Attack Surface + Remediation */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Attack Surface */}
                <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-2"><Network className="w-5 h-5 text-blue-500" /><h3 className="text-gray-900 dark:text-white text-lg font-bold">Attack Surface</h3></div>
                        <button onClick={() => navigate('/attack-surface')} className="text-sm text-blue-600 dark:text-blue-500 hover:text-blue-500">View →</button>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mb-6">
                        {[
                            { label: 'Assets', value: assets?.total ?? 0, accent: 'text-gray-900 dark:text-white' },
                            { label: 'Active', value: assets?.active ?? 0, accent: 'text-green-600 dark:text-green-400' },
                            { label: 'Drift', value: assets?.inactive ?? 0, accent: 'text-gray-500' },
                        ].map((s) => (
                            <div key={s.label} className="bg-gray-50 dark:bg-gray-800/40 rounded-xl p-4 border border-gray-200 dark:border-gray-800">
                                <p className="text-xs text-gray-500 uppercase mb-1">{s.label}</p>
                                <p className={`text-2xl font-bold ${s.accent}`}>{s.value}</p>
                            </div>
                        ))}
                    </div>
                    <div className="flex-1 flex flex-col justify-center">
                        <p className="text-xs text-gray-500 uppercase mb-4">Composition by type</p>
                        {Object.keys(assets?.byType || {}).length === 0 ? (
                            <p className="text-sm text-gray-500">No assets discovered yet.</p>
                        ) : (
                            <div className="space-y-4">
                                {Object.entries(assets.byType).map(([t, c]) => (
                                    <div key={t} className="flex items-center gap-3">
                                        <span className="text-xs text-gray-500 w-20 shrink-0">{ASSET_LABEL[t] || t}</span>
                                        <div className="flex-1 h-2.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                                            <div className="h-full bg-blue-500/70 rounded-full transition-all duration-700" style={{ width: `${(Number(c) / assetMaxType) * 100}%` }} />
                                        </div>
                                        <span className="text-xs font-mono text-gray-700 dark:text-gray-300 w-8 text-right">{Number(c)}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>

                {/* Remediation SLA */}
                <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-2"><ClipboardList className="w-5 h-5 text-blue-500" /><h3 className="text-gray-900 dark:text-white text-lg font-bold">Remediation</h3></div>
                        <button onClick={() => navigate('/remediation')} className="text-sm text-blue-600 dark:text-blue-500 hover:text-blue-500">View →</button>
                    </div>
                    <div className="grid grid-cols-2 gap-4 mb-6">
                        <div className="bg-gray-50 dark:bg-gray-800/40 rounded-xl p-4 border border-gray-200 dark:border-gray-800">
                            <p className="text-xs text-gray-500 uppercase mb-1">Open Tickets</p>
                            <p className="text-2xl font-bold text-gray-900 dark:text-white">{remStats?.open ?? 0}</p>
                        </div>
                        <div className="bg-red-50 dark:bg-red-500/5 rounded-xl p-4 border border-red-200 dark:border-red-500/20">
                            <p className="text-xs text-red-600/80 dark:text-red-400/80 uppercase mb-1">SLA Breached</p>
                            <p className="text-2xl font-bold text-red-600 dark:text-red-400">{remStats?.breached ?? 0}</p>
                        </div>
                    </div>
                    <div className="flex-1 flex flex-col justify-center">
                        <p className="text-xs text-gray-500 uppercase mb-2">Status breakdown</p>
                        {(() => {
                            const segs = [
                                { st: 'todo', color: 'bg-gray-400', dot: 'bg-gray-400' },
                                { st: 'in_progress', color: 'bg-blue-500', dot: 'bg-blue-500' },
                                { st: 'blocked', color: 'bg-amber-500', dot: 'bg-amber-500' },
                                { st: 'done', color: 'bg-green-500', dot: 'bg-green-500' },
                            ];
                            const total = segs.reduce((a, s) => a + (remStats?.byStatus?.[s.st] ?? 0), 0);
                            return (
                                <>
                                    <div className="flex h-2.5 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800 mb-5">
                                        {total > 0 ? segs.map((s) => {
                                            const c = remStats?.byStatus?.[s.st] ?? 0;
                                            return c > 0 ? <div key={s.st} className={s.color} style={{ width: `${(c / total) * 100}%` }} /> : null;
                                        }) : null}
                                    </div>
                                    <div className="space-y-3">
                                        {segs.map((s) => (
                                            <div key={s.st} className="flex items-center justify-between text-sm">
                                                <span className="flex items-center gap-2 text-gray-600 dark:text-gray-300"><span className={`w-2.5 h-2.5 rounded-full ${s.dot}`} />{REM_LABEL[s.st]}</span>
                                                <span className="font-mono text-gray-700 dark:text-gray-200">{remStats?.byStatus?.[s.st] ?? 0}</span>
                                            </div>
                                        ))}
                                    </div>
                                </>
                            );
                        })()}
                    </div>
                </div>
            </div>

            {/* Scan Activity */}
            <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Scan Activity</h3>
                <p className="text-sm text-gray-500 mb-6">Last 7 days</p>
                <div ref={chartWrapRef} className="h-[220px]"><LineChart /></div>
                <div className="flex justify-center gap-6 mt-3">
                    <div className="flex items-center gap-2 text-xs text-gray-500"><div className="w-2 h-2 rounded-full bg-blue-500" /> Total</div>
                    <div className="flex items-center gap-2 text-xs text-gray-500"><div className="w-2 h-2 rounded-full bg-green-500" /> Completed</div>
                </div>
                <div className="grid grid-cols-4 gap-3 mt-5 pt-5 border-t border-gray-200 dark:border-gray-800">
                    {[
                        { label: 'Total', value: scanCounts.total, accent: 'text-gray-900 dark:text-white' },
                        { label: 'Completed', value: scanCounts.completed, accent: 'text-green-600 dark:text-green-400' },
                        { label: 'Failed', value: scanCounts.failed, accent: 'text-red-600 dark:text-red-400' },
                        { label: 'Running', value: scanCounts.running, accent: 'text-blue-600 dark:text-blue-400' },
                    ].map((c) => (
                        <div key={c.label} className="text-center">
                            <p className={`text-xl font-bold ${c.accent}`}>{c.value}</p>
                            <p className="text-[10px] text-gray-500 uppercase mt-0.5">{c.label}</p>
                        </div>
                    ))}
                </div>
            </div>

            {/* Recent Scans */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="p-6 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white">Recent Scans</h3>
                        <p className="text-sm text-gray-500">Latest security scan results</p>
                    </div>
                    <button onClick={() => navigate('/scan/history')} className="text-sm text-blue-600 dark:text-blue-500 hover:text-blue-500 dark:hover:text-blue-400">View all scans →</button>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-6 py-4 font-medium">Scan ID</th>
                                <th className="px-6 py-4 font-medium">Target</th>
                                <th className="px-6 py-4 font-medium">Status</th>
                                <th className="px-6 py-4 font-medium">Findings</th>
                                <th className="px-6 py-4 font-medium">Time</th>
                                <th className="px-6 py-4 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {recentScans.map((scan) => (
                                <tr key={scan.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer" onClick={() => navigate(viewPath(scan))}>
                                    <td className="px-6 py-4 text-sm font-mono text-blue-600 dark:text-blue-500">#{scan.scan_number}</td>
                                    <td className="px-6 py-4 text-sm text-gray-900 dark:text-white font-medium max-w-xs"><ScrollText>{scan.target}</ScrollText></td>
                                    <td className="px-6 py-4">
                                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                                            scan.status === 'Completed' ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-500 border-green-200 dark:border-green-500/20' :
                                            scan.status === 'Failed' ? 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-500 border-red-200 dark:border-red-500/20' :
                                            'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-500 border-blue-200 dark:border-blue-500/20'}`}>
                                            {scan.status === 'Completed' && <CheckCircle className="w-3 h-3 mr-1" />}
                                            {scan.status === 'Failed' && <AlertTriangle className="w-3 h-3 mr-1" />}
                                            {scan.status === 'Running' && <Activity className="w-3 h-3 mr-1 animate-pulse" />}
                                            {scan.status}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <div className="flex items-center gap-3 text-xs font-mono">
                                            <span className="text-red-600 dark:text-red-500">C:{scan.findings.Critical}</span>
                                            <span className="text-orange-600 dark:text-orange-500">H:{scan.findings.High}</span>
                                            <span className="text-yellow-600 dark:text-yellow-500">M:{scan.findings.Medium}</span>
                                            <span className="text-blue-600 dark:text-blue-500">L:{scan.findings.Low}</span>
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                                        <div className="flex items-center gap-1"><Clock className="w-3 h-3" />{relTime(scan.date)}</div>
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <button onClick={(e) => { e.stopPropagation(); navigate(viewPath(scan)); }}
                                            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white">
                                            <Eye className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {recentScans.length === 0 && (
                                <tr><td colSpan={6} className="px-6 py-8 text-center text-gray-500">No scans found. Start your first scan!</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageTransition>
    );
};

export default Dashboard;
