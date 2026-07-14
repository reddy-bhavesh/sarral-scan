import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
    Bot, ArrowLeft, Square, Cpu, Terminal, CheckCircle, AlertTriangle,
    Activity, Download, Target as TargetIcon, SkipForward,
} from 'lucide-react';
import api from '../api/axios';
import { useSSE } from '../context/SSEContext';

const STAGES = ['Scoping', 'Discovery', 'Prioritization', 'Validation', 'Mobilization'];

const fmtStage = (s?: string | null) => s || '—';

// Per-stage accent used for the timeline node + stage label.
const STAGE_STYLES: Record<string, { dot: string; text: string; chip: string }> = {
    Scoping:        { dot: 'bg-sky-500',     text: 'text-sky-600 dark:text-sky-400',         chip: 'bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300' },
    Discovery:      { dot: 'bg-blue-500',    text: 'text-blue-600 dark:text-blue-400',       chip: 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-300' },
    Prioritization: { dot: 'bg-violet-500',  text: 'text-violet-600 dark:text-violet-400',   chip: 'bg-violet-50 dark:bg-violet-500/10 text-violet-700 dark:text-violet-300' },
    Validation:     { dot: 'bg-amber-500',   text: 'text-amber-600 dark:text-amber-400',     chip: 'bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-300' },
    Mobilization:   { dot: 'bg-emerald-500', text: 'text-emerald-600 dark:text-emerald-400', chip: 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-300' },
};
const stageStyle = (s?: string | null) =>
    (s && STAGE_STYLES[s]) || { dot: 'bg-gray-400', text: 'text-gray-500', chip: 'bg-gray-100 dark:bg-gray-800 text-gray-500' };

const AiScanView = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { addEventListener, removeEventListener } = useSSE();
    const [scan, setScan] = useState<any>(null);
    const [decisions, setDecisions] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [stopping, setStopping] = useState(false);
    const termRef = useRef<HTMLDivElement>(null);

    const fetchAll = useCallback(async () => {
        try {
            const [s, d] = await Promise.all([
                api.get(`/scans/${id}`),
                api.get(`/ctem/scans/${id}/agent-decisions`),
            ]);
            setScan(s.data);
            setDecisions(Array.isArray(d.data) ? d.data : []);
        } catch (e) {
            console.error('fetch AI scan failed', e);
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // Live: any SCAN_UPDATE for this scan triggers a refetch.
    useEffect(() => {
        const onUpdate = (data: any) => {
            if (data && Number(data.scanId) === Number(id)) fetchAll();
        };
        addEventListener('SCAN_UPDATE', onUpdate);
        return () => removeEventListener('SCAN_UPDATE', onUpdate);
    }, [id, addEventListener, removeEventListener, fetchAll]);

    // Poll while running (fallback to SSE).
    useEffect(() => {
        const t = setInterval(() => {
            if (scan && scan.status === 'Running') fetchAll();
        }, 2500);
        return () => clearInterval(t);
    }, [scan?.status, fetchAll]);

    // Auto-scroll terminal to bottom on new output.
    const results = (scan?.results || [])
        .filter((r: any) => r.tool !== 'AI_PHASE_SUMMARY')
        .sort((a: any, b: any) => a.id - b.id);
    useEffect(() => {
        if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
    }, [results.length, scan?.status]);

    const stop = async () => {
        setStopping(true);
        try { await api.post(`/scans/${id}/stop`); fetchAll(); }
        catch (e) { console.error(e); } finally { setStopping(false); }
    };

    if (loading) {
        return <div className="flex items-center justify-center h-[60vh]"><div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-500" /></div>;
    }
    if (!scan) return <div className="text-gray-500">Scan not found.</div>;

    const running = scan.status === 'Running';
    const stagesSeen = new Set(decisions.map((d) => d.ctemStage).filter(Boolean));
    const currentStage = decisions.length ? decisions[decisions.length - 1].ctemStage : 'Scoping';

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                    <button onClick={() => navigate(-1)} className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-500"><ArrowLeft className="w-5 h-5" /></button>
                    <Bot className="w-6 h-6 text-blue-500" />
                    <div>
                        <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <TargetIcon className="w-4 h-4 text-gray-400" />{scan.target}
                            <span className={`ml-1 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                                scan.status === 'Completed' ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-400 border-green-200 dark:border-green-500/20' :
                                scan.status === 'Failed' ? 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20' :
                                scan.status === 'Stopped' ? 'bg-gray-100 dark:bg-gray-700/40 text-gray-500 border-gray-200 dark:border-gray-600' :
                                'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20'}`}>
                                {running && <Activity className="w-3 h-3 mr-1 animate-pulse" />}{scan.status}
                            </span>
                        </h1>
                        {scan.objective && <p className="text-sm text-gray-500 mt-0.5 max-w-2xl truncate">{scan.objective}</p>}
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {scan.pdfPath && (
                        <a href={`/reports/${scan.pdfPath.split(/[\\/]/).pop()}`} target="_blank" rel="noreferrer"
                            className="px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm text-gray-600 dark:text-gray-300 flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-800">
                            <Download className="w-4 h-4" /> Report
                        </a>
                    )}
                    {running && (
                        <button onClick={stop} disabled={stopping}
                            className="px-4 py-2 rounded-lg bg-red-600 text-white text-sm font-medium flex items-center gap-2 hover:bg-red-700 disabled:opacity-50">
                            <Square className="w-4 h-4 fill-current" /> {stopping ? 'Stopping...' : 'Stop'}
                        </button>
                    )}
                </div>
            </div>

            {/* CTEM stage stepper */}
            <div className="flex items-center gap-2 mb-4 flex-wrap">
                {STAGES.map((s, i) => {
                    const done = stagesSeen.has(s);
                    const active = s === currentStage && running;
                    return (
                        <div key={s} className="flex items-center">
                            <span className={`px-3 py-1 rounded-full text-xs font-medium border ${
                                active ? 'bg-blue-600 text-white border-blue-600' :
                                done ? 'bg-blue-50 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20' :
                                'bg-gray-50 dark:bg-gray-900 text-gray-400 border-gray-200 dark:border-gray-800'}`}>
                                {s}
                            </span>
                            {i < STAGES.length - 1 && <span className="mx-1 text-gray-300 dark:text-gray-700">→</span>}
                        </div>
                    );
                })}
            </div>

            {/* Two-pane: timeline + terminal */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 flex-1 min-h-0">
                {/* Left: agent timeline */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col min-h-0">
                    <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
                        <Cpu className="w-4 h-4 text-blue-500" /><span className="text-sm font-semibold text-gray-900 dark:text-white">Agent Timeline</span>
                        <span className="text-xs text-gray-400">({decisions.length})</span>
                    </div>
                    <div className="px-4 py-4 overflow-y-auto flex-1 space-y-3">
                        {decisions.length === 0 ? (
                            <p className="text-sm text-gray-500">Waiting for the agent's first decision…</p>
                        ) : decisions.map((d) => {
                            const st = stageStyle(d.ctemStage);
                            return (
                                <div key={d.id} className="relative rounded-lg border border-gray-200 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-800/30 overflow-hidden">
                                    {/* stage accent stripe */}
                                    <span className={`absolute left-0 top-0 bottom-0 w-1 ${d.done ? 'bg-emerald-500' : st.dot}`} aria-hidden />
                                    <div className="pl-4 pr-3 py-3">
                                        {/* header */}
                                        <div className="flex items-center gap-2 mb-2">
                                            <span className="text-xs font-bold text-gray-400 tabular-nums">#{d.stepIndex}</span>
                                            <span className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded ${st.chip}`}>{fmtStage(d.ctemStage)}</span>
                                            {d.tool && <span className="text-xs font-mono font-semibold text-gray-700 dark:text-gray-200">{d.tool}</span>}
                                            <span className="flex-1" />
                                            {d.confidence != null && <span className="text-[10px] text-gray-400 tabular-nums">{Math.round(d.confidence * 100)}%</span>}
                                            {d.modelUsed && <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-200 dark:bg-gray-800 text-gray-500 dark:text-gray-400">{d.modelUsed}</span>}
                                            {d.done && <CheckCircle className="w-4 h-4 text-emerald-500" />}
                                        </div>
                                        {/* reasoning */}
                                        {d.reasoning && <p className="text-[13px] leading-relaxed text-gray-600 dark:text-gray-300 mb-2.5">{d.reasoning}</p>}
                                        {/* command */}
                                        {d.authoredCommand && (
                                            <div className="text-[11px] font-mono bg-gray-900 dark:bg-gray-950 border border-gray-700/50 dark:border-gray-800 text-emerald-400 rounded-md px-2.5 py-1.5 overflow-x-auto custom-scrollbar whitespace-nowrap">
                                                <span className="text-gray-500 select-none mr-1.5">$</span>{d.authoredCommand}
                                            </div>
                                        )}
                                        {/* expectation */}
                                        {d.expectation && (
                                            <p className="flex gap-1.5 text-[11px] leading-relaxed text-gray-500 dark:text-gray-400 mt-2">
                                                <span className={`shrink-0 font-bold ${st.text}`}>→</span>
                                                <span>{d.expectation}</span>
                                            </p>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Right: live terminal */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col min-h-0">
                    <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-blue-500" /><span className="text-sm font-semibold text-gray-900 dark:text-white">Terminal</span>
                        <span className="text-xs text-gray-400">({results.length} commands)</span>
                    </div>
                    <div ref={termRef} className="p-4 overflow-y-auto flex-1 bg-gray-950 rounded-b-xl font-mono text-xs">
                        {results.length === 0 ? (
                            <p className="text-gray-500">No commands run yet.</p>
                        ) : results.map((r: any) => (
                            <div key={r.id} className="mb-4">
                                <div className="flex items-center gap-2 text-blue-400">
                                    <span className="text-gray-500">$</span>
                                    <span className="break-all">{r.command}</span>
                                    {r.status === 'Running' && <Activity className="w-3 h-3 animate-pulse text-yellow-400" />}
                                    {r.status === 'Completed' && <CheckCircle className="w-3 h-3 text-green-500" />}
                                    {r.status === 'Failed' && <AlertTriangle className="w-3 h-3 text-red-500" />}
                                    {r.status === 'Skipped' && <SkipForward className="w-3 h-3 text-gray-500" />}
                                </div>
                                <pre className="text-gray-300 whitespace-pre-wrap break-all mt-1 leading-relaxed">{r.raw_output}</pre>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AiScanView;
