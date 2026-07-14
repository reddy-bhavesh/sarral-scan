import { useState, useEffect, useCallback } from 'react';
import PageTransition from '../components/PageTransition';
import {
    ShieldAlert, Flame, Clock, AlertTriangle, Gauge, Search,
    ChevronLeft, ChevronRight, ExternalLink,
} from 'lucide-react';
import api from '../api/axios';
import ScrollText from '../components/ScrollText';

const SEVERITIES = ['Critical', 'High', 'Medium', 'Low', 'Info'];

const sevClass = (s: string) => ({
    Critical: 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
    High: 'bg-orange-100 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-500/20',
    Medium: 'bg-yellow-100 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/20',
    Low: 'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20',
    Info: 'bg-gray-100 dark:bg-gray-700/40 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600',
}[s] || 'bg-gray-100 text-gray-600 border-gray-200');

const riskColor = (score: number | null) => {
    if (score == null) return 'text-gray-400';
    if (score >= 85) return 'text-red-600 dark:text-red-400';
    if (score >= 70) return 'text-orange-600 dark:text-orange-400';
    if (score >= 50) return 'text-yellow-600 dark:text-yellow-400';
    return 'text-blue-600 dark:text-blue-400';
};

const fmtDate = (d: string | null) => (d ? new Date(d).toLocaleDateString() : '—');

const KpiCard = ({ icon: Icon, label, value, accent }: any) => (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
        <div className="flex items-center justify-between">
            <span className="text-xs uppercase tracking-wide text-gray-500">{label}</span>
            <Icon className={`w-4 h-4 ${accent}`} />
        </div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{value}</div>
    </div>
);

const Exposures = () => {
    const [summary, setSummary] = useState<any>(null);
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [severity, setSeverity] = useState<string>('');
    const [kevOnly, setKevOnly] = useState(false);
    const [search, setSearch] = useState('');
    const [sort, setSort] = useState('risk_desc');
    const limit = 20;

    const fetchSummary = useCallback(async () => {
        try {
            const res = await api.get('/ctem/exposures/summary');
            setSummary(res.data);
        } catch (e) { console.error('summary failed', e); }
    }, []);

    const fetchExposures = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/ctem/exposures', {
                params: { page, limit, severity: severity || undefined, kevOnly, search: search || undefined, sort },
            });
            setItems(Array.isArray(res.data?.items) ? res.data.items : []);
            setTotalPages(res.data?.pages || 1);
        } catch (e) {
            console.error('exposures failed', e);
        } finally {
            setLoading(false);
        }
    }, [page, severity, kevOnly, search, sort]);

    useEffect(() => { fetchSummary(); }, [fetchSummary]);
    useEffect(() => { fetchExposures(); }, [fetchExposures]);

    const triage = async (id: number, status: string) => {
        try {
            await api.patch(`/ctem/findings/${id}/status`, { status });
            fetchExposures();
            fetchSummary();
        } catch (e) { console.error('triage failed', e); }
    };

    return (
        <PageTransition>
            <div className="mb-6">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Exposures</h1>
                <p className="text-sm text-gray-500 mt-1">
                    Prioritized findings — what to fix and by when, ranked by risk (CVSS · EPSS · KEV · asset criticality).
                </p>
            </div>

            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                    <KpiCard icon={ShieldAlert} label="Open" value={summary.totalOpen} accent="text-blue-500" />
                    <KpiCard icon={Flame} label="Known Exploited" value={summary.kevCount} accent="text-red-500" />
                    <KpiCard icon={AlertTriangle} label="Overdue" value={summary.overdueCount} accent="text-red-500" />
                    <KpiCard icon={Clock} label="Due ≤ 7d" value={summary.dueSoonCount} accent="text-orange-500" />
                    <KpiCard icon={Gauge} label="Avg Risk" value={summary.avgRiskScore} accent="text-purple-500" />
                </div>
            )}

            {/* Filters */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
                <div className="flex gap-1">
                    <button
                        onClick={() => { setSeverity(''); setPage(1); }}
                        className={`px-3 py-1.5 rounded-lg text-sm border ${!severity ? 'bg-blue-600 text-white border-blue-600' : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-800'}`}
                    >All</button>
                    {SEVERITIES.map((s) => (
                        <button
                            key={s}
                            onClick={() => { setSeverity(s); setPage(1); }}
                            className={`px-3 py-1.5 rounded-lg text-sm border ${severity === s ? 'bg-blue-600 text-white border-blue-600' : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-800'}`}
                        >{s}</button>
                    ))}
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300 cursor-pointer">
                    <input type="checkbox" checked={kevOnly} onChange={(e) => { setKevOnly(e.target.checked); setPage(1); }} />
                    KEV only
                </label>
                <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="risk_desc">Risk (high → low)</option>
                    <option value="risk_asc">Risk (low → high)</option>
                    <option value="sla_asc">Fix by (soonest)</option>
                    <option value="sla_desc">Fix by (latest)</option>
                    <option value="newest">Newest</option>
                    <option value="oldest">Oldest</option>
                </select>
                <div className="relative ml-auto">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                    <input
                        value={search}
                        onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                        placeholder="Search title / CVE..."
                        className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-900 dark:text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:border-blue-500 w-64 shadow-sm text-sm"
                    />
                </div>
            </div>

            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-4 py-3 font-medium">Risk</th>
                                <th className="px-4 py-3 font-medium">Severity</th>
                                <th className="px-4 py-3 font-medium">Finding</th>
                                <th className="px-4 py-3 font-medium">Asset</th>
                                <th className="px-4 py-3 font-medium">CVE</th>
                                <th className="px-4 py-3 font-medium">Fix by</th>
                                <th className="px-4 py-3 font-medium text-right">Triage</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {loading ? (
                                <tr><td colSpan={7} className="px-6 py-12 text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                                </td></tr>
                            ) : items.length === 0 ? (
                                <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                    No exposures found. Run a scan (then optionally <code>backfill_findings.py</code>) to populate.
                                </td></tr>
                            ) : items.map((f) => (
                                <tr key={f.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <td className={`px-4 py-3 font-mono font-bold ${riskColor(f.riskScore)}`}>
                                        {f.riskScore != null ? f.riskScore : '—'}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${sevClass(f.severity)}`}>{f.severity}</span>
                                    </td>
                                    <td className="px-4 py-3 max-w-xs">
                                        <ScrollText className="text-sm text-gray-900 dark:text-white font-medium">{f.title}</ScrollText>
                                        <div className="text-xs text-gray-500">{f.tool}{f.phase ? ` · ${f.phase}` : ''}</div>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300 font-mono max-w-[14rem]">
                                        {f.asset ? <ScrollText>{f.asset.value}</ScrollText> : '—'}
                                    </td>
                                    <td className="px-4 py-3 text-xs">
                                        {f.cveId ? (
                                            <div className="flex flex-col gap-1">
                                                <a
                                                    href={`https://nvd.nist.gov/vuln/detail/${f.cveId}`}
                                                    target="_blank" rel="noreferrer"
                                                    className="text-blue-600 dark:text-blue-400 font-mono inline-flex items-center gap-1"
                                                >{f.cveId}<ExternalLink className="w-3 h-3" /></a>
                                                <div className="flex gap-1 flex-wrap">
                                                    {f.cve?.cvssV3Score != null && <span className="px-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">CVSS {f.cve.cvssV3Score}</span>}
                                                    {f.cve?.epssScore != null && <span className="px-1.5 rounded bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300">EPSS {(f.cve.epssScore * 100).toFixed(0)}%</span>}
                                                    {f.cve?.isKev && <span className="px-1.5 rounded bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400 font-semibold">KEV</span>}
                                                </div>
                                                {(() => {
                                                    const extras = (f.cves || []).filter((c: any) => (c.cveId || '').toUpperCase() !== (f.cveId || '').toUpperCase());
                                                    if (!extras.length) return null;
                                                    return (
                                                        <div className="flex flex-wrap items-center gap-1 mt-0.5">
                                                            <span className="text-[10px] text-gray-400 uppercase">also</span>
                                                            {extras.slice(0, 4).map((c: any) => (
                                                                <a key={c.cveId} href={`https://nvd.nist.gov/vuln/detail/${c.cveId}`} target="_blank" rel="noreferrer"
                                                                    title={`${c.cveId}${c.cvssV3Score != null ? ` · CVSS ${c.cvssV3Score}` : ''}${c.isKev ? ' · KEV' : ''}`}
                                                                    className={`px-1.5 rounded font-mono hover:underline ${c.isKev ? 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-400' : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'}`}>
                                                                    {(c.cveId || '').replace(/^CVE-/i, '')}
                                                                </a>
                                                            ))}
                                                            {extras.length > 4 && <span className="text-gray-400">+{extras.length - 4}</span>}
                                                        </div>
                                                    );
                                                })()}
                                            </div>
                                        ) : <span className="text-gray-400">—</span>}
                                    </td>
                                    <td className="px-4 py-3 text-sm">
                                        <span className={f.overdue ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-600 dark:text-gray-300'}>
                                            {fmtDate(f.slaDueDate)}{f.overdue ? ' ⚠' : ''}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <select
                                            value={f.status}
                                            onChange={(e) => triage(f.id, e.target.value)}
                                            className="text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 text-gray-700 dark:text-gray-200 focus:outline-none"
                                        >
                                            <option value="open">Open</option>
                                            <option value="reopened">Reopened</option>
                                            <option value="remediated">Remediated</option>
                                            <option value="accepted">Accepted</option>
                                            <option value="false_positive">False positive</option>
                                        </select>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {!loading && totalPages > 1 && (
                        <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-gray-200 dark:border-gray-800">
                            <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}
                                className="p-2 border border-gray-200 dark:border-gray-800 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 text-gray-500">
                                <ChevronLeft className="w-4 h-4" />
                            </button>
                            <span className="text-sm text-gray-700 dark:text-gray-300 px-2">Page {page} of {totalPages}</span>
                            <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page === totalPages}
                                className="p-2 border border-gray-200 dark:border-gray-800 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 text-gray-500">
                                <ChevronRight className="w-4 h-4" />
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </PageTransition>
    );
};

export default Exposures;
