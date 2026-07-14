import { useState, useEffect, useCallback, useMemo } from 'react';
import PageTransition from '../components/PageTransition';
import { Network, Search, ChevronDown, ChevronRight, Globe, Server, Link2, Box } from 'lucide-react';
import api from '../api/axios';
import ScrollText from '../components/ScrollText';

const typeIcon = (t: string) => ({
    domain: Globe, subdomain: Globe, ip: Server, url: Link2, service: Box,
}[t] || Box);

const fmtDate = (d: string) => (d ? new Date(d).toLocaleDateString() : '—');

// Group key = the registrable host of an asset's root target (scheme/port/path stripped),
// so every subdomain/IP/URL discovered under a domain collapses under one accordion.
const groupKey = (a: any): string => {
    let r = String(a.rootTarget || a.value || '').toLowerCase();
    r = r.replace(/^[a-z][a-z0-9+.-]*:\/\//, '').split('/')[0].split(':')[0];
    return r || String(a.value || '').toLowerCase();
};

const StatCard = ({ label, value, accent }: any) => (
    <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4 shadow-sm">
        <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
        <div className={`text-2xl font-bold mt-2 ${accent || 'text-gray-900 dark:text-white'}`}>{value}</div>
    </div>
);

const AttackSurface = () => {
    const [summary, setSummary] = useState<any>(null);
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [assetType, setAssetType] = useState('');
    const [activeFilter, setActiveFilter] = useState<string>('true'); // 'true' | 'false' | ''
    const [search, setSearch] = useState('');
    const [sort, setSort] = useState('lastSeen_desc');
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    const fetchSummary = useCallback(async () => {
        try {
            const res = await api.get('/ctem/assets/summary');
            setSummary(res.data);
        } catch (e) { console.error(e); }
    }, []);

    const fetchAssets = useCallback(async () => {
        setLoading(true);
        try {
            // Fetch the full set and group client-side (the surface is small; grouped
            // accordions replace pagination as the way to manage volume).
            const params: any = { page: 1, limit: 2000, search: search || undefined, sort };
            if (assetType) params.assetType = assetType;
            if (activeFilter !== '') params.active = activeFilter === 'true';
            const res = await api.get('/ctem/assets', { params });
            setItems(Array.isArray(res.data?.items) ? res.data.items : []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, [assetType, activeFilter, search, sort]);

    useEffect(() => { fetchSummary(); }, [fetchSummary]);
    useEffect(() => { fetchAssets(); }, [fetchAssets]);

    const groups = useMemo(() => {
        const map = new Map<string, any[]>();
        for (const a of items) {
            const k = groupKey(a);
            if (!map.has(k)) map.set(k, []);
            map.get(k)!.push(a);
        }
        const arr = Array.from(map.entries()).map(([root, assets]) => ({
            root,
            assets,
            count: assets.length,
            openFindings: assets.reduce((s, a) => s + (a.findingCount || 0), 0),
            active: assets.filter((a) => a.isActive).length,
            lastSeen: assets.reduce((m, a) => (a.lastSeen && a.lastSeen > m ? a.lastSeen : m), ''),
        }));
        // Most-exposed domains first, then largest, then alphabetical.
        arr.sort((a, b) => b.openFindings - a.openFindings || b.count - a.count || a.root.localeCompare(b.root));
        return arr;
    }, [items]);

    const searching = search.trim().length > 0;
    const toggle = (root: string) => setExpanded((prev) => {
        const next = new Set(prev);
        next.has(root) ? next.delete(root) : next.add(root);
        return next;
    });
    const expandAll = () => setExpanded(new Set(groups.map((g) => g.root)));
    const collapseAll = () => setExpanded(new Set());

    return (
        <PageTransition>
            <div className="mb-6 flex items-center gap-3">
                <Network className="w-6 h-6 text-blue-500" />
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Attack Surface</h1>
                    <p className="text-sm text-gray-500 mt-1">Persistent inventory of discovered assets, grouped by domain and tracked across scans for drift.</p>
                </div>
            </div>

            {summary && (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <StatCard label="Total Assets" value={summary.total} />
                    <StatCard label="Active" value={summary.active} accent="text-green-600 dark:text-green-400" />
                    <StatCard label="Inactive (drift)" value={summary.inactive} accent="text-gray-500" />
                    <StatCard label="Domains" value={groups.length} />
                </div>
            )}

            <div className="flex flex-wrap items-center gap-3 mb-4">
                <select value={assetType} onChange={(e) => setAssetType(e.target.value)}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="">All types</option>
                    <option value="domain">Domain</option>
                    <option value="subdomain">Subdomain</option>
                    <option value="ip">IP</option>
                    <option value="url">URL</option>
                    <option value="service">Service</option>
                </select>
                <select value={activeFilter} onChange={(e) => setActiveFilter(e.target.value)}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="true">Active</option>
                    <option value="false">Inactive</option>
                    <option value="">All</option>
                </select>
                <select value={sort} onChange={(e) => setSort(e.target.value)}
                    className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-700 dark:text-gray-200 rounded-lg px-3 py-2 text-sm">
                    <option value="lastSeen_desc">Last seen (newest)</option>
                    <option value="lastSeen_asc">Last seen (oldest)</option>
                    <option value="firstSeen_desc">First seen (newest)</option>
                    <option value="firstSeen_asc">First seen (oldest)</option>
                    <option value="value_asc">Asset (A–Z)</option>
                    <option value="value_desc">Asset (Z–A)</option>
                </select>
                {!searching && groups.length > 0 && (
                    <button onClick={() => (expanded.size === groups.length ? collapseAll() : expandAll())}
                        className="text-sm text-blue-600 dark:text-blue-400 hover:underline px-1">
                        {expanded.size === groups.length ? 'Collapse all' : 'Expand all'}
                    </button>
                )}
                <div className="relative ml-auto">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
                    <input value={search} onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search assets..."
                        className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-900 dark:text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:border-blue-500 w-64 shadow-sm text-sm" />
                </div>
            </div>

            {loading ? (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm py-16 text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                </div>
            ) : groups.length === 0 ? (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm py-16 text-center text-gray-500">
                    No assets yet. Run a scan with recon/discovery phases to populate the inventory.
                </div>
            ) : (
                <div className="space-y-3">
                    {groups.map((g) => {
                        const isOpen = searching || expanded.has(g.root);
                        return (
                            <div key={g.root} className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                                {/* Domain header */}
                                <button onClick={() => toggle(g.root)}
                                    className="w-full flex items-center justify-between px-4 py-3.5 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <div className="flex items-center gap-3 min-w-0">
                                        {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400 shrink-0" /> : <ChevronRight className="w-4 h-4 text-gray-400 shrink-0" />}
                                        <Globe className="w-4 h-4 text-blue-500 shrink-0" />
                                        <span className="font-mono font-semibold text-gray-900 dark:text-white truncate">{g.root}</span>
                                        <span className="text-xs text-gray-500 shrink-0">{g.count} asset{g.count !== 1 ? 's' : ''}</span>
                                    </div>
                                    <div className="flex items-center gap-4 text-xs shrink-0 pl-3">
                                        {g.openFindings > 0 && (
                                            <span className="text-orange-600 dark:text-orange-400 font-semibold">{g.openFindings} open finding{g.openFindings !== 1 ? 's' : ''}</span>
                                        )}
                                        <span className="text-gray-500 hidden sm:inline">Last seen {fmtDate(g.lastSeen)}</span>
                                    </div>
                                </button>

                                {/* Assets under this domain */}
                                {isOpen && (
                                    <div className="border-t border-gray-200 dark:border-gray-800 overflow-x-auto">
                                        <table className="w-full text-left border-collapse">
                                            <thead>
                                                <tr className="bg-gray-50 dark:bg-gray-900/50 text-[11px] uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                                    <th className="px-4 py-2.5 font-medium">Type</th>
                                                    <th className="px-4 py-2.5 font-medium">Asset</th>
                                                    <th className="px-4 py-2.5 font-medium">State</th>
                                                    <th className="px-4 py-2.5 font-medium">Open Findings</th>
                                                    <th className="px-4 py-2.5 font-medium">First Seen</th>
                                                    <th className="px-4 py-2.5 font-medium">Last Seen</th>
                                                </tr>
                                            </thead>
                                            <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                                                {g.assets.map((a) => {
                                                    const Icon = typeIcon(a.assetType);
                                                    return (
                                                        <tr key={a.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors">
                                                            <td className="px-4 py-3">
                                                                <span className="inline-flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
                                                                    <Icon className="w-3.5 h-3.5" />{a.assetType}
                                                                </span>
                                                            </td>
                                                            <td className="px-4 py-3 text-sm font-mono text-gray-900 dark:text-white max-w-[18rem]"><ScrollText>{a.value}</ScrollText></td>
                                                            <td className="px-4 py-3">
                                                                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium border ${a.isActive
                                                                    ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20'
                                                                    : 'bg-gray-100 dark:bg-gray-700/40 text-gray-500 border-gray-200 dark:border-gray-600'}`}>
                                                                    {a.isActive ? 'Active' : 'Inactive'}
                                                                </span>
                                                            </td>
                                                            <td className="px-4 py-3 text-sm font-mono">
                                                                {a.findingCount > 0
                                                                    ? <span className="text-orange-600 dark:text-orange-400 font-semibold">{a.findingCount}</span>
                                                                    : <span className="text-gray-400">0</span>}
                                                            </td>
                                                            <td className="px-4 py-3 text-sm text-gray-500">{fmtDate(a.firstSeen)}</td>
                                                            <td className="px-4 py-3 text-sm text-gray-500">{fmtDate(a.lastSeen)}</td>
                                                        </tr>
                                                    );
                                                })}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}
        </PageTransition>
    );
};

export default AttackSurface;
