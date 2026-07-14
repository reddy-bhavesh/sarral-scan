import { useState, useEffect } from 'react';
import PageTransition from '../components/PageTransition';
import { ShieldCheck, Plus, Trash2, Power, AlertTriangle, Loader2, Building2 } from 'lucide-react';
import api from '../api/axios';

interface Engagement {
    id: number;
    org: string;
    inScope: string[];
    exclusions: string[];
    approver?: string | null;
    expiresAt?: string | null;
    isActive: boolean;
    notes?: string | null;
    createdAt: string;
    updatedAt: string;
}

const blankForm = { org: '', inScope: '', exclusions: '', approver: '', expiresAt: '', notes: '' };

const Engagements = () => {
    const [items, setItems] = useState<Engagement[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [form, setForm] = useState({ ...blankForm });
    const [saving, setSaving] = useState(false);

    const load = async () => {
        setLoading(true);
        try {
            const r = await api.get('/engagements/');
            setItems(Array.isArray(r.data) ? r.data : []);
        } catch {
            setError('Failed to load engagements.');
        } finally {
            setLoading(false);
        }
    };
    useEffect(() => { load(); }, []);

    const splitList = (s: string) => s.split(/[\n,]/).map((x) => x.trim()).filter(Boolean);

    const create = async () => {
        setError('');
        if (!form.org.trim()) return setError('Organization is required.');
        const inScope = splitList(form.inScope);
        if (inScope.length === 0) return setError('At least one in-scope host/domain is required.');
        setSaving(true);
        try {
            await api.post('/engagements/', {
                org: form.org.trim(),
                inScope,
                exclusions: splitList(form.exclusions),
                approver: form.approver.trim() || null,
                expiresAt: form.expiresAt ? new Date(form.expiresAt).toISOString() : null,
                notes: form.notes.trim() || null,
            });
            setForm({ ...blankForm });
            await load();
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to create engagement.');
        } finally {
            setSaving(false);
        }
    };

    const toggleActive = async (e: Engagement) => {
        try {
            await api.patch(`/engagements/${e.id}`, { isActive: !e.isActive });
            await load();
        } catch {
            setError('Failed to update engagement.');
        }
    };

    const remove = async (id: number) => {
        if (!confirm('Delete this engagement? Deep scans bound to it will no longer be authorized.')) return;
        try {
            await api.delete(`/engagements/${id}`);
            await load();
        } catch {
            setError('Failed to delete engagement.');
        }
    };

    const expired = (e: Engagement) => !!e.expiresAt && new Date(e.expiresAt) < new Date();

    const input = 'w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500';
    const labelC = 'block text-xs font-medium text-gray-500 mb-1 uppercase';

    return (
        <PageTransition className="max-w-6xl mx-auto space-y-6">
            <div className="flex items-center gap-3">
                <div className="bg-blue-600 p-2 rounded-lg"><ShieldCheck className="w-6 h-6 text-white" /></div>
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Authorized Engagements</h1>
                    <p className="text-gray-500 dark:text-gray-400 text-sm">
                        Register the organizations and scopes you are authorized to test. Deep Agent scans only run against an active engagement.
                    </p>
                </div>
            </div>

            {error && (
                <div className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg p-3 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4" />{error}
                </div>
            )}

            {/* Create form */}
            <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm space-y-4">
                <div className="flex items-center gap-2"><Plus className="w-5 h-5 text-blue-600 dark:text-blue-500" />
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">New Engagement</h2></div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className={labelC}>Organization *</label>
                        <input className={input} value={form.org} onChange={(e) => setForm({ ...form, org: e.target.value })} placeholder="Acme Corp" /></div>
                    <div><label className={labelC}>Approved By</label>
                        <input className={input} value={form.approver} onChange={(e) => setForm({ ...form, approver: e.target.value })} placeholder="name / email / ticket" /></div>
                    <div><label className={labelC}>In-Scope * (comma or newline separated)</label>
                        <textarea className={input} rows={2} value={form.inScope} onChange={(e) => setForm({ ...form, inScope: e.target.value })} placeholder="example.com, *.example.com, 10.0.0.0/24" /></div>
                    <div><label className={labelC}>Exclusions</label>
                        <textarea className={input} rows={2} value={form.exclusions} onChange={(e) => setForm({ ...form, exclusions: e.target.value })} placeholder="billing.example.com" /></div>
                    <div><label className={labelC}>Valid Until (optional)</label>
                        <input type="date" className={input} value={form.expiresAt} onChange={(e) => setForm({ ...form, expiresAt: e.target.value })} /></div>
                    <div><label className={labelC}>Notes</label>
                        <input className={input} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="optional" /></div>
                </div>
                <button onClick={create} disabled={saving}
                    className="px-5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium flex items-center gap-2 disabled:opacity-50">
                    {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create Engagement
                </button>
            </div>

            {/* List */}
            <div className="space-y-3">
                {loading ? (
                    <div className="flex items-center gap-2 text-gray-500"><Loader2 className="w-4 h-4 animate-spin" /> Loading…</div>
                ) : items.length === 0 ? (
                    <p className="text-sm text-gray-500">No engagements yet. Create one above to enable Deep Agent scans.</p>
                ) : items.map((e) => (
                    <div key={e.id} className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-5 shadow-sm">
                        <div className="flex items-start justify-between">
                            <div className="flex items-center gap-2">
                                <Building2 className="w-5 h-5 text-gray-400" />
                                <span className="font-semibold text-gray-900 dark:text-white">{e.org}</span>
                                {e.isActive && !expired(e)
                                    ? <span className="px-2 py-0.5 text-[10px] rounded-full bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400">ACTIVE</span>
                                    : <span className="px-2 py-0.5 text-[10px] rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300">{expired(e) ? 'EXPIRED' : 'INACTIVE'}</span>}
                            </div>
                            <div className="flex items-center gap-2">
                                <button onClick={() => toggleActive(e)} title="Toggle active"
                                    className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"><Power className="w-4 h-4" /></button>
                                <button onClick={() => remove(e.id)} title="Delete"
                                    className="p-2 rounded-lg hover:bg-red-50 dark:hover:bg-red-500/10 text-red-500"><Trash2 className="w-4 h-4" /></button>
                            </div>
                        </div>
                        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-600 dark:text-gray-400">
                            <div><span className="font-medium text-gray-500 uppercase">In-Scope: </span>{e.inScope.join(', ') || '—'}</div>
                            <div><span className="font-medium text-gray-500 uppercase">Exclusions: </span>{e.exclusions.join(', ') || '—'}</div>
                            <div><span className="font-medium text-gray-500 uppercase">Approver: </span>{e.approver || '—'}</div>
                            <div><span className="font-medium text-gray-500 uppercase">Valid Until: </span>{e.expiresAt ? new Date(e.expiresAt).toLocaleDateString() : 'no expiry'}</div>
                        </div>
                    </div>
                ))}
            </div>
        </PageTransition>
    );
};

export default Engagements;
