import { useState, useEffect, useCallback } from 'react';
import PageTransition from '../components/PageTransition';
import { ClipboardList, AlertTriangle } from 'lucide-react';
import api from '../api/axios';

const STATUSES = ['todo', 'in_progress', 'blocked', 'done', 'wont_fix'];
const STATUS_LABEL: Record<string, string> = {
    todo: 'To Do', in_progress: 'In Progress', blocked: 'Blocked', done: 'Done', wont_fix: "Won't Fix",
};

const sevClass = (s: string) => ({
    Critical: 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20',
    High: 'bg-orange-100 dark:bg-orange-500/10 text-orange-700 dark:text-orange-400 border-orange-200 dark:border-orange-500/20',
    Medium: 'bg-yellow-100 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-500/20',
    Low: 'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20',
    Info: 'bg-gray-100 dark:bg-gray-700/40 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600',
}[s] || 'bg-gray-100 text-gray-600 border-gray-200');

const fmtDate = (d: string | null) => (d ? new Date(d).toLocaleDateString() : '—');

const SEV_RANK: Record<string, number> = { Critical: 5, High: 4, Medium: 3, Low: 2, Info: 1 };
const ts = (d: string | null) => (d ? new Date(d).getTime() : Number.POSITIVE_INFINITY);

const Remediation = () => {
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [statusFilter, setStatusFilter] = useState('');
    const [sort, setSort] = useState('due_asc');

    const fetchRems = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/ctem/remediations', {
                params: { status: statusFilter || undefined },
            });
            setItems(Array.isArray(res.data) ? res.data : []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [statusFilter]);

    useEffect(() => { fetchRems(); }, [fetchRems]);

    const update = async (id: number, status: string) => {
        try {
            await api.patch(`/ctem/remediations/${id}`, { status });
            fetchRems();
        } catch (e) { console.error(e); }
    };

    const openCount = items.filter((r) => !['done', 'wont_fix'].includes(r.status)).length;
    const breachedCount = items.filter((r) => r.slaBreached).length;

    const sortedItems = [...items].sort((a, b) => {
        const fa = a.finding || {}, fb = b.finding || {};
        switch (sort) {
            case 'due_desc': return ts(b.dueDate) - ts(a.dueDate);
            case 'risk_desc': return (fb.riskScore ?? -1) - (fa.riskScore ?? -1);
            case 'risk_asc': return (fa.riskScore ?? Infinity) - (fb.riskScore ?? Infinity);
            case 'severity': return (SEV_RANK[fb.severity] ?? 0) - (SEV_RANK[fa.severity] ?? 0);
            case 'due_asc':
            default: return ts(a.dueDate) - ts(b.dueDate);
        }
    });

    return (
        <PageTransition>
            <div className="mb-6 flex items-center gap-3">
                <ClipboardList className="w-6 h-6 text-blue-500" />
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Remediation</h1>
                    <p className="text-sm text-gray-500 mt-1">Tickets auto-opened for high-risk exposures, with SLA due dates.</p>
                </div>
            </div>

            <div className="flex items-center gap-3 mb-4">
                <div className="text-sm text-gray-600 dark:text-gray-300">
                    <span className="font-semibold">{openCount}</span> open
                    {breachedCount > 0 && (
                        <span className="ml-3 inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                            <AlertTriangle className="w-4 h-4" />{breachedCount} SLA breached
                        </span>
                    )}
                </div>
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}
                    className="ml-auto bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">All statuses</option>
                    {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                </select>
                <select value={sort} onChange={(e) => setSort(e.target.value)}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="due_asc">Due (soonest)</option>
                    <option value="due_desc">Due (latest)</option>
                    <option value="risk_desc">Risk (high → low)</option>
                    <option value="risk_asc">Risk (low → high)</option>
                    <option value="severity">Severity (high → low)</option>
                </select>
            </div>

            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-4 py-3 font-medium">Severity</th>
                                <th className="px-4 py-3 font-medium">Finding</th>
                                <th className="px-4 py-3 font-medium">Asset</th>
                                <th className="px-4 py-3 font-medium">Risk</th>
                                <th className="px-4 py-3 font-medium">Due</th>
                                <th className="px-4 py-3 font-medium text-right">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {loading ? (
                                <tr><td colSpan={6} className="px-6 py-12 text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                                </td></tr>
                            ) : items.length === 0 ? (
                                <tr><td colSpan={6} className="px-6 py-12 text-center text-gray-500">
                                    No remediation tickets yet. They're auto-created for Critical/High/KEV findings after a scan.
                                </td></tr>
                            ) : sortedItems.map((r) => {
                                const f = r.finding || {};
                                return (
                                    <tr key={r.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                        <td className="px-4 py-3">
                                            <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${sevClass(f.severity)}`}>{f.severity || '—'}</span>
                                        </td>
                                        <td className="px-4 py-3 max-w-xs">
                                            <div className="text-sm text-gray-900 dark:text-white font-medium truncate">{f.title || '—'}</div>
                                            {f.cveId && <div className="text-xs font-mono text-blue-600 dark:text-blue-400">{f.cveId}{f.cve?.isKev ? ' · KEV' : ''}</div>}
                                        </td>
                                        <td className="px-4 py-3 text-sm font-mono text-gray-600 dark:text-gray-300">{f.asset ? f.asset.value : '—'}</td>
                                        <td className="px-4 py-3 text-sm font-mono text-gray-700 dark:text-gray-200">{f.riskScore != null ? f.riskScore : '—'}</td>
                                        <td className="px-4 py-3 text-sm">
                                            <span className={r.slaBreached ? 'text-red-600 dark:text-red-400 font-semibold' : 'text-gray-600 dark:text-gray-300'}>
                                                {fmtDate(r.dueDate)}{r.slaBreached ? ' ⚠' : ''}
                                            </span>
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <select value={r.status} onChange={(e) => update(r.id, e.target.value)}
                                                className="text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 text-gray-700 dark:text-gray-200 focus:outline-none">
                                                {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                                            </select>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageTransition>
    );
};

export default Remediation;
