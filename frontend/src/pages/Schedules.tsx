import { useState, useEffect, useCallback } from 'react';
import PageTransition from '../components/PageTransition';
import { CalendarClock, Play, Trash2, Plus, Power } from 'lucide-react';
import api from '../api/axios';

const PHASES = ['Passive Recon', 'Active Recon', 'Asset Discovery', 'Enumeration', 'Vulnerability Analysis'];
const FREQUENCIES = ['hourly', 'daily', 'weekly', 'monthly'];

const fmt = (d: string | null) => (d ? new Date(d).toLocaleString() : '—');

const pad2 = (n: number) => String(n).padStart(2, '0');
// The backend stores atTime as UTC "HH:MM"; the picker works in the user's local time.
const localToUtcHHMM = (t: string): string | undefined => {
    if (!t) return undefined;
    const [h, m] = t.split(':').map(Number);
    const d = new Date(); d.setHours(h, m, 0, 0);
    return `${pad2(d.getUTCHours())}:${pad2(d.getUTCMinutes())}`;
};
const utcToLocalHHMM = (t?: string | null): string => {
    if (!t) return '';
    const [h, m] = t.split(':').map(Number);
    const d = new Date(); d.setUTCHours(h, m, 0, 0);
    return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
};

const Schedules = () => {
    const [items, setItems] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);

    // form state
    const [target, setTarget] = useState('');
    const [phases, setPhases] = useState<string[]>(['Passive Recon']);
    const [frequency, setFrequency] = useState('daily');
    const [mode, setMode] = useState('classic');
    const [atTime, setAtTime] = useState<string>('');
    const [startInMinutes, setStartInMinutes] = useState<string>('');
    const [submitting, setSubmitting] = useState(false);

    const fetchSchedules = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/schedules');
            setItems(Array.isArray(res.data) ? res.data : []);
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchSchedules(); }, [fetchSchedules]);

    const togglePhase = (p: string) =>
        setPhases((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));

    const create = async () => {
        if (!target || phases.length === 0) return;
        setSubmitting(true);
        try {
            await api.post('/schedules', {
                target, phases, frequency, mode,
                atTime: frequency === 'hourly' ? undefined : localToUtcHHMM(atTime),
                startInMinutes: startInMinutes ? parseInt(startInMinutes, 10) : undefined,
            });
            setTarget(''); setPhases(['Passive Recon']); setFrequency('daily');
            setMode('classic'); setAtTime(''); setStartInMinutes(''); setShowForm(false);
            fetchSchedules();
        } catch (e) {
            console.error(e); alert('Failed to create schedule');
        } finally {
            setSubmitting(false);
        }
    };

    const toggleEnabled = async (s: any) => {
        try { await api.patch(`/schedules/${s.id}`, { isEnabled: !s.isEnabled }); fetchSchedules(); }
        catch (e) { console.error(e); }
    };

    const runNow = async (id: number) => {
        try { await api.post(`/schedules/${id}/run`); fetchSchedules(); }
        catch (e) { console.error(e); alert('Failed to launch'); }
    };

    const remove = async (id: number) => {
        if (!window.confirm('Delete this schedule?')) return;
        try { await api.delete(`/schedules/${id}`); fetchSchedules(); }
        catch (e) { console.error(e); }
    };

    return (
        <PageTransition>
            <div className="mb-6 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <CalendarClock className="w-6 h-6 text-blue-500" />
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Scheduled Scans</h1>
                        <p className="text-sm text-gray-500 mt-1">Continuous monitoring — recurring scans keep the attack surface and exposures current.</p>
                    </div>
                </div>
                <button onClick={() => setShowForm((v) => !v)}
                    className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium flex items-center gap-2 hover:bg-blue-700 transition-colors">
                    <Plus className="w-4 h-4" /> New Schedule
                </button>
            </div>

            {showForm && (
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 shadow-sm mb-6 space-y-4">
                    <div>
                        <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Target</label>
                        <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="example.com"
                            className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500" />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Frequency</label>
                            <select value={frequency} onChange={(e) => setFrequency(e.target.value)}
                                className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg">
                                {FREQUENCIES.map((f) => <option key={f} value={f}>{f}</option>)}
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Time of day</label>
                            <input value={atTime} onChange={(e) => setAtTime(e.target.value)} type="time"
                                disabled={frequency === 'hourly'}
                                className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg disabled:opacity-50" />
                            <p className="text-[10px] text-gray-400 mt-1">{frequency === 'hourly' ? 'N/A for hourly' : 'Your local time'}</p>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Mode</label>
                            <select value={mode} onChange={(e) => setMode(e.target.value)}
                                className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg">
                                <option value="classic">Classic</option>
                                <option value="agentic">Agentic (AI-guided)</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">First run in (min)</label>
                            <input value={startInMinutes} onChange={(e) => setStartInMinutes(e.target.value)} placeholder="default: one interval" type="number"
                                className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg" />
                        </div>
                    </div>
                    <div>
                        <label className="block text-xs font-medium text-gray-500 mb-2 uppercase">Phases</label>
                        <div className="flex flex-wrap gap-2">
                            {PHASES.map((p) => (
                                <button key={p} onClick={() => togglePhase(p)}
                                    className={`px-3 py-1.5 rounded-lg text-sm border ${phases.includes(p)
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-800'}`}>
                                    {p}
                                </button>
                            ))}
                        </div>
                    </div>
                    <div className="flex justify-end gap-2">
                        <button onClick={() => setShowForm(false)} className="px-4 py-2 rounded-lg text-sm text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-800">Cancel</button>
                        <button onClick={create} disabled={submitting || !target || phases.length === 0}
                            className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
                            {submitting ? 'Creating...' : 'Create Schedule'}
                        </button>
                    </div>
                </div>
            )}

            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-4 py-3 font-medium">Target</th>
                                <th className="px-4 py-3 font-medium">Frequency</th>
                                <th className="px-4 py-3 font-medium">Mode</th>
                                <th className="px-4 py-3 font-medium">Next Run</th>
                                <th className="px-4 py-3 font-medium">Last Run</th>
                                <th className="px-4 py-3 font-medium">State</th>
                                <th className="px-4 py-3 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {loading ? (
                                <tr><td colSpan={7} className="px-6 py-12 text-center">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                                </td></tr>
                            ) : items.length === 0 ? (
                                <tr><td colSpan={7} className="px-6 py-12 text-center text-gray-500">No schedules yet. Create one to enable continuous monitoring.</td></tr>
                            ) : items.map((s) => (
                                <tr key={s.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                    <td className="px-4 py-3 text-sm font-mono text-gray-900 dark:text-white">{s.target}
                                        <div className="text-xs text-gray-400 font-sans truncate max-w-xs">{s.phases}</div>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">
                                        {s.frequency}{s.atTime ? <span className="text-gray-400"> · {utcToLocalHHMM(s.atTime)}</span> : ''}
                                    </td>
                                    <td className="px-4 py-3 text-sm">
                                        <span className={`px-2 py-0.5 rounded-full text-xs border ${s.mode === 'agentic'
                                            ? 'bg-purple-100 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-200 dark:border-purple-500/20'
                                            : 'bg-gray-100 dark:bg-gray-700/40 text-gray-600 dark:text-gray-300 border-gray-200 dark:border-gray-600'}`}>{s.mode}</span>
                                    </td>
                                    <td className="px-4 py-3 text-sm text-gray-600 dark:text-gray-300">{fmt(s.nextRunAt)}</td>
                                    <td className="px-4 py-3 text-sm text-gray-500">{fmt(s.lastRunAt)}</td>
                                    <td className="px-4 py-3">
                                        <button onClick={() => toggleEnabled(s)}
                                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${s.isEnabled
                                                ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20'
                                                : 'bg-gray-100 dark:bg-gray-700/40 text-gray-500 border-gray-200 dark:border-gray-600'}`}>
                                            <Power className="w-3 h-3" />{s.isEnabled ? 'Enabled' : 'Disabled'}
                                        </button>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <button onClick={() => runNow(s.id)} title="Run now"
                                                className="p-2 text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 hover:bg-blue-50 dark:hover:bg-blue-500/10 rounded-lg transition-colors">
                                                <Play className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => remove(s.id)} title="Delete"
                                                className="p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors">
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageTransition>
    );
};

export default Schedules;
