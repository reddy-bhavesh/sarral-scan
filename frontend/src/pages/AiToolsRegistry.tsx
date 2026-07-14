import { useState, useEffect, useCallback } from 'react';
import PageTransition from '../components/PageTransition';
import Modal from '../components/Modal';
import { Wrench, Plus, Trash2, Pencil, Sparkles, Power } from 'lucide-react';
import api from '../api/axios';

interface AiTool {
    id: number;
    name: string;
    binary: string;
    description: string;
    usageNotes?: string | null;
    isEnabled: boolean;
}

const empty = { name: '', binary: '', description: '', usageNotes: '', isEnabled: true };

const AiToolsRegistry = () => {
    const [tools, setTools] = useState<AiTool[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [editing, setEditing] = useState<AiTool | null>(null);
    const [form, setForm] = useState<any>(empty);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');

    const fetchTools = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/ai-tools/');
            setTools(Array.isArray(res.data) ? res.data : []);
        } catch (e) { console.error(e); } finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchTools(); }, [fetchTools]);

    const openCreate = () => { setEditing(null); setForm(empty); setError(''); setShowForm(true); };
    const openEdit = (t: AiTool) => {
        setEditing(t);
        setForm({ name: t.name, binary: t.binary, description: t.description, usageNotes: t.usageNotes || '', isEnabled: t.isEnabled });
        setError(''); setShowForm(true);
    };

    const save = async () => {
        if (!form.name.trim() || !form.binary.trim() || !form.description.trim()) {
            setError('Name, binary and description are required.'); return;
        }
        setSaving(true); setError('');
        try {
            if (editing) await api.patch(`/ai-tools/${editing.id}`, form);
            else await api.post('/ai-tools/', form);
            setShowForm(false);
            fetchTools();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Failed to save tool');
        } finally { setSaving(false); }
    };

    const remove = async (id: number) => {
        if (!window.confirm('Delete this tool?')) return;
        try { await api.delete(`/ai-tools/${id}`); fetchTools(); } catch (e) { console.error(e); }
    };

    const toggle = async (t: AiTool) => {
        try { await api.patch(`/ai-tools/${t.id}`, { isEnabled: !t.isEnabled }); fetchTools(); }
        catch (e) { console.error(e); }
    };

    const seedDefaults = async () => {
        try { await api.post('/ai-tools/seed-defaults'); fetchTools(); } catch (e) { console.error(e); }
    };

    return (
        <PageTransition>
            <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <Wrench className="w-6 h-6 text-blue-500" />
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI Tools</h1>
                        <p className="text-sm text-gray-500 mt-1">Tools the AI-Guided agent may use. It authors each command from your description + usage hints.</p>
                    </div>
                </div>
                <div className="flex gap-2">
                    <button onClick={seedDefaults}
                        className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800">
                        <Sparkles className="w-4 h-4" /> Seed defaults
                    </button>
                    <button onClick={openCreate}
                        className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium flex items-center gap-2 hover:bg-blue-700">
                        <Plus className="w-4 h-4" /> Add tool
                    </button>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-4 py-3 font-medium">Name</th>
                                <th className="px-4 py-3 font-medium">Binary</th>
                                <th className="px-4 py-3 font-medium">Description</th>
                                <th className="px-4 py-3 font-medium">State</th>
                                <th className="px-4 py-3 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {loading ? (
                                <tr><td colSpan={5} className="px-6 py-12 text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                                </td></tr>
                            ) : tools.length === 0 ? (
                                <tr><td colSpan={5} className="px-6 py-12 text-center text-gray-500">
                                    No tools yet. Click <span className="font-medium">Seed defaults</span> to add a common Kali set, or add your own.
                                </td></tr>
                            ) : tools.map((t) => (
                                <tr key={t.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-white">{t.name}</td>
                                    <td className="px-4 py-3 text-sm font-mono text-blue-600 dark:text-blue-400">{t.binary}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500 max-w-md truncate">{t.description}</td>
                                    <td className="px-4 py-3">
                                        <button onClick={() => toggle(t)}
                                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${t.isEnabled
                                                ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20'
                                                : 'bg-gray-100 dark:bg-gray-700/40 text-gray-500 border-gray-200 dark:border-gray-600'}`}>
                                            <Power className="w-3 h-3" />{t.isEnabled ? 'Enabled' : 'Disabled'}
                                        </button>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <button onClick={() => openEdit(t)} title="Edit"
                                                className="p-2 text-gray-400 hover:text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded-lg"><Pencil className="w-4 h-4" /></button>
                                            <button onClick={() => remove(t.id)} title="Delete"
                                                className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg"><Trash2 className="w-4 h-4" /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <Modal isOpen={showForm} onClose={() => setShowForm(false)} title={editing ? 'Edit tool' : 'Add tool'}>
                <div className="space-y-4">
                    {error && <div className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg p-3">{error}</div>}
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Name</label>
                            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                                className="w-full bg-gray-950 border border-gray-800 text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500" placeholder="Nmap" />
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Binary</label>
                            <input value={form.binary} onChange={(e) => setForm({ ...form, binary: e.target.value })}
                                className="w-full bg-gray-950 border border-gray-800 text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500 font-mono" placeholder="nmap" />
                        </div>
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Description (fed to the AI)</label>
                        <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2}
                            className="w-full bg-gray-950 border border-gray-800 text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500" placeholder="Network/port scanner with service + version detection." />
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-400 mb-1 uppercase">Usage notes / hints (optional)</label>
                        <textarea value={form.usageNotes} onChange={(e) => setForm({ ...form, usageNotes: e.target.value })} rows={3}
                            className="w-full bg-gray-950 border border-gray-800 text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500 font-mono text-sm" placeholder="e.g. nmap -sV -p- --open <host>; add --script vuln for NSE checks." />
                    </div>
                    <label className="flex items-center gap-2 text-sm text-gray-300">
                        <input type="checkbox" checked={form.isEnabled} onChange={(e) => setForm({ ...form, isEnabled: e.target.checked })} /> Enabled
                    </label>
                    <div className="flex justify-end gap-2 pt-2">
                        <button onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-sm text-gray-300 border border-gray-700">Cancel</button>
                        <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                            {saving ? 'Saving...' : (editing ? 'Save' : 'Add tool')}
                        </button>
                    </div>
                </div>
            </Modal>
        </PageTransition>
    );
};

export default AiToolsRegistry;
