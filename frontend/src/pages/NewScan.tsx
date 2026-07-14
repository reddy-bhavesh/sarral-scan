import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import { Target, Search, AlertTriangle, CheckCircle, Loader2, Play, ArrowLeft, Bot, ListChecks, Crosshair, ShieldAlert, Wrench, ShieldCheck } from 'lucide-react';
import api from '../api/axios';

interface AiTool { id: number; name: string; binary: string; description: string; isEnabled: boolean; }
interface Engagement { id: number; org: string; inScope: string[]; exclusions: string[]; isActive: boolean; expiresAt?: string | null; }

// Deep Agent specialists (keys must match backend services/deep_agent/specialists.py)
const DEEP_SPECIALISTS = [
    { key: 'recon', name: 'Recon & Asset Discovery', desc: 'Subdomains, DNS, web tech, live hosts (run first).' },
    { key: 'nmap', name: 'Network / Port (Nmap)', desc: 'Ports, services, NSE vuln scripts.' },
    { key: 'sqli', name: 'SQL Injection', desc: 'SQLMap against live web hosts.' },
    { key: 'xss', name: 'Cross-Site Scripting', desc: 'Dalfox against live web hosts.' },
    { key: 'nuclei', name: 'CVE & Misconfiguration', desc: 'Nuclei template scanning.' },
    { key: 'fuzzing', name: 'Content Discovery', desc: 'FFUF directory/content brute-force.' },
    { key: 'dos', name: 'DoS-Resilience (non-destructive)', desc: 'Amplification + missing rate-limit detection. No flooding.' },
    { key: 'weblogic', name: 'Web-Logic Flaws', desc: 'SSRF / XXE / LFI / traversal detection.' },
    { key: 'bruteforce', name: 'Credential Brute-Force', desc: 'Authorized, rate-limited login testing.' },
    { key: 'tls', name: 'TLS / WAF / Headers', desc: 'TLS config, WAF, security headers.' },
];

const NewScan = () => {
    const navigate = useNavigate();
    const [target, setTarget] = useState('');
    const [mode, setMode] = useState<'classic' | 'agentic' | 'deep'>('classic');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [sshStatus, setSshStatus] = useState<'checking' | 'connected' | 'error'>('checking');
    const [sshMessage, setSshMessage] = useState('');

    // Classic
    const [selectedPhases, setSelectedPhases] = useState<string[]>([]);

    // AI-Guided
    const [aiTools, setAiTools] = useState<AiTool[]>([]);
    const [selectedToolIds, setSelectedToolIds] = useState<number[]>([]);
    const [objective, setObjective] = useState('');
    const [exclusions, setExclusions] = useState('');
    const [maxCommands, setMaxCommands] = useState('15');
    const [maxSeconds, setMaxSeconds] = useState('3600');
    const [perCmdTimeout, setPerCmdTimeout] = useState('600');
    const [ack, setAck] = useState(false);

    // Deep Agent
    const [engagements, setEngagements] = useState<Engagement[]>([]);
    const [engagementId, setEngagementId] = useState<number | null>(null);
    const [selectedSpecialists, setSelectedSpecialists] = useState<string[]>(DEEP_SPECIALISTS.map((s) => s.key));

    const phases = {
        'Reconnaissance': [
            { id: 'Passive Recon', description: 'Gather information without directly interacting with the target', tools: ['Whois', 'NSLookup', 'Subfinder (Passive)', 'Assetfinder', 'WebScraperRecon'] },
            { id: 'Active Recon', description: 'Actively probe the target for information', tools: ['Nmap Top 1000', 'WhatWeb', 'WafW00f', 'Nmap WAF Detection', 'WhatWaf', 'SSLScan'] },
        ],
        'Discovery': [
            { id: 'Asset Discovery', description: 'Discover all assets related to the target', tools: ['Subfinder (Full)', 'DNS Resolver', 'Alive Web Hosts'] },
            { id: 'Enumeration', description: 'Enumerate services and directories', tools: ['FFUF', 'Nmap Vulnerability Scan'] },
        ],
        'Vulnerability': [
            { id: 'Vulnerability Analysis', description: 'Scan for known vulnerabilities', tools: ['SQLMap', 'Dalfox', 'Nuclei'] },
        ],
    };

    const checkSSH = async () => {
        setSshStatus('checking'); setSshMessage('');
        try {
            const { data } = await api.get('/system/status');
            const isReady = data.tools_ready || data.ssh_connection;
            if (isReady) { setSshStatus('connected'); setSshMessage(data.message || 'System ready'); }
            else { setSshStatus('error'); setSshMessage(data.message || 'System not ready. Please check configuration.'); }
        } catch {
            setSshStatus('error'); setSshMessage('Failed to check system status. Backend might be down.');
        }
    };

    useEffect(() => { checkSSH(); }, []);
    useEffect(() => {
        (async () => {
            try {
                const r = await api.get('/ai-tools/');
                setAiTools((Array.isArray(r.data) ? r.data : []).filter((t: AiTool) => t.isEnabled));
            } catch { /* ignore */ }
        })();
    }, []);
    useEffect(() => {
        (async () => {
            try {
                const r = await api.get('/engagements/');
                const list: Engagement[] = (Array.isArray(r.data) ? r.data : [])
                    .filter((e: Engagement) => e.isActive && (!e.expiresAt || new Date(e.expiresAt) > new Date()));
                setEngagements(list);
                if (list.length > 0) setEngagementId((prev) => prev ?? list[0].id);
            } catch { /* ignore */ }
        })();
    }, []);

    const togglePhase = (p: string) =>
        setSelectedPhases((prev) => (prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]));
    const toggleTool = (id: number) =>
        setSelectedToolIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

    const allPhaseIds = Object.values(phases).flat().map((p) => p.id);
    const allPhasesSelected = allPhaseIds.length > 0 && selectedPhases.length === allPhaseIds.length;
    const toggleAllPhases = () => setSelectedPhases(allPhasesSelected ? [] : allPhaseIds);

    const allToolsSelected = aiTools.length > 0 && selectedToolIds.length === aiTools.length;
    const toggleAllTools = () => setSelectedToolIds(allToolsSelected ? [] : aiTools.map((t) => t.id));

    // Deep mode: prefill the target from the engagement when it names a concrete host
    // (not a wildcard/CIDR). For wildcard scopes the user still types the specific host.
    const selectedEngagement = engagements.find((e) => e.id === engagementId) || null;
    useEffect(() => {
        if (mode !== 'deep' || !selectedEngagement || target.trim()) return;
        const concrete = selectedEngagement.inScope.find((h) => !h.startsWith('*.') && !h.includes('/'));
        if (concrete) setTarget(concrete);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [mode, engagementId, engagements]);

    const toggleSpecialist = (key: string) =>
        setSelectedSpecialists((prev) => (prev.includes(key) ? prev.filter((x) => x !== key) : [...prev, key]));
    const allSpecialistsSelected = selectedSpecialists.length === DEEP_SPECIALISTS.length;
    const toggleAllSpecialists = () => setSelectedSpecialists(allSpecialistsSelected ? [] : DEEP_SPECIALISTS.map((s) => s.key));

    const classicReady = !!target.trim() && selectedPhases.length > 0;
    const agenticReady = !!target.trim() && !!objective.trim() && selectedToolIds.length > 0 && ack;
    const deepReady = !!target.trim() && engagementId != null && selectedSpecialists.length > 0 && ack;
    const canLaunch = sshStatus !== 'error' && !loading &&
        (mode === 'classic' ? classicReady : mode === 'agentic' ? agenticReady : deepReady);

    const handleSubmit = async (e: React.FormEvent | React.MouseEvent) => {
        e.preventDefault();
        setError('');
        if (mode === 'classic') {
            if (!classicReady) return;
            setLoading(true);
            try {
                const res = await api.post('/scans/', { target: target.trim(), phases: selectedPhases, mode: 'classic' });
                navigate(`/scan/${res.data.id}`);
            } catch (err: any) {
                setError(err?.response?.data?.detail || 'Failed to start scan');
            } finally { setLoading(false); }
            return;
        }
        if (mode === 'deep') {
            if (!target.trim()) return setError('Target is required.');
            if (engagementId == null) return setError('Select an authorized engagement.');
            if (selectedSpecialists.length === 0) return setError('Select at least one specialist.');
            if (!ack) return setError('Please confirm you are authorized to test this target.');
            setLoading(true);
            try {
                const res = await api.post('/scans/', {
                    target: target.trim(), phases: [], mode: 'deep',
                    engagementId, selectedSpecialists,
                });
                navigate(`/deep-scan/${res.data.id}`);
            } catch (err: any) {
                setError(err?.response?.data?.detail || 'Failed to start deep scan');
            } finally { setLoading(false); }
            return;
        }
        // Agentic / AI-Guided
        if (!target.trim()) return setError('Target is required.');
        if (!objective.trim()) return setError('Objective is required for AI-Guided mode.');
        if (selectedToolIds.length === 0) return setError('Select at least one tool for the agent to use.');
        if (!ack) return setError('Please confirm you are authorized to test this target.');
        setLoading(true);
        try {
            const res = await api.post('/ai-scans/', {
                target: target.trim(),
                objective: objective.trim(),
                toolIds: selectedToolIds,
                constraints: {
                    in_scope: [target.trim()],
                    exclusions: exclusions.split(',').map((s) => s.trim()).filter(Boolean),
                    max_commands: parseInt(maxCommands, 10) || 15,
                    max_seconds: parseInt(maxSeconds, 10) || 3600,
                    per_command_timeout: parseInt(perCmdTimeout, 10) || 600,
                },
            });
            navigate(`/ai-scan/${res.data.id}`);
        } catch (err: any) {
            setError(err?.response?.data?.detail || 'Failed to launch AI scan');
        } finally { setLoading(false); }
    };

    const totalPhases = Object.values(phases).reduce((acc, group) => acc + group.length, 0);

    return (
        <PageTransition className="relative">
            {/* Fixed Header */}
            <div className="fixed top-0 right-0 left-64 z-20 px-8 py-4 bg-white/95 dark:bg-gray-950/95 backdrop-blur supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-gray-950/60 border-b border-gray-200 dark:border-gray-800">
                <div className="max-w-6xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button onClick={() => navigate(-1)}
                            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white">
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Start New Scan</h1>
                            <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
                                {mode === 'agentic' ? 'AI agent authors and runs commands toward your objective'
                                    : mode === 'deep' ? 'Orchestrator delegates to attack-type specialist agents within an authorized engagement'
                                    : 'Configure and launch a comprehensive security scan'}
                            </p>
                        </div>
                    </div>
                    <button onClick={handleSubmit} disabled={!canLaunch}
                        className={`px-6 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-all ${
                            !canLaunch ? 'bg-red-600/50 text-white/50 cursor-not-allowed' : 'btn-cta'}`}>
                        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
                        {mode === 'agentic' ? 'Launch AI Scan' : mode === 'deep' ? 'Launch Deep Agent' : 'Launch Scan'}
                    </button>
                </div>
            </div>

            <div className="h-24"></div>

            <div className="max-w-6xl mx-auto space-y-6">
                {/* Connection status */}
                {sshStatus === 'checking' && (
                    <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-xl p-4 flex items-center gap-3 text-blue-600 dark:text-blue-400">
                        <Loader2 className="w-5 h-5 animate-spin" /><span>Checking connection to Kali VM...</span>
                    </div>
                )}
                {sshStatus === 'connected' && (
                    <div className="bg-green-50 dark:bg-green-500/5 border border-green-200 dark:border-green-500/10 rounded-xl p-4 flex items-center gap-3">
                        <div className="p-1 rounded-full bg-green-100 dark:bg-green-500/10"><CheckCircle className="w-5 h-5 text-green-600 dark:text-green-500" /></div>
                        <div>
                            <p className="text-green-700 dark:text-green-500 font-medium text-sm">Connection Successful</p>
                            <p className="text-green-600/80 dark:text-green-500/60 text-xs">{sshMessage}</p>
                        </div>
                    </div>
                )}
                {sshStatus === 'error' && (
                    <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl p-4 flex items-center justify-between text-red-600 dark:text-red-400">
                        <div className="flex items-center gap-3"><AlertTriangle className="w-5 h-5" /><div><p className="font-medium">Connection Error</p><p className="text-sm opacity-90">{sshMessage}</p></div></div>
                        <button onClick={checkSSH} className="px-4 py-2 bg-red-100 dark:bg-red-500/20 hover:bg-red-200 dark:hover:bg-red-500/30 rounded-lg text-sm font-medium transition-colors">Retry</button>
                    </div>
                )}
                {error && <div className="text-sm text-red-500 bg-red-500/10 border border-red-500/20 rounded-lg p-3">{error}</div>}

                {/* Target */}
                <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-6"><Target className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Target Configuration</h2></div>
                    <label className="block text-xs font-medium text-gray-500 mb-2 uppercase">Target URL or IP Address</label>
                    <input type="text" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="example.com or 192.168.1.1"
                        className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-4 py-3 rounded-lg focus:outline-none focus:border-blue-500 transition-colors placeholder-gray-400 dark:placeholder-gray-600" />
                    {mode === 'deep' && (
                        <p className="text-xs text-gray-400 mt-2">
                            The specific host to scan this run. It must fall within the selected engagement's scope
                            {selectedEngagement ? ` (${selectedEngagement.inScope.join(', ')})` : ''}.
                            {selectedEngagement && ' Prefilled from the engagement when it names a single host — edit for a specific subdomain.'}
                        </p>
                    )}
                </div>

                {/* Scan Mode */}
                <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                    <div className="flex items-center gap-2 mb-6"><Bot className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Scan Mode</h2></div>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        {[
                            { id: 'classic', icon: ListChecks, title: 'Classic', desc: 'Runs every selected tool in a fixed pipeline. Deterministic and exhaustive.' },
                            { id: 'agentic', icon: Bot, title: 'Agentic (AI-guided)', desc: 'An AI agent authors and runs commands toward your objective, through the CTEM cycle, within your scope.' },
                            { id: 'deep', icon: ShieldCheck, title: 'Deep Agent (multi-specialist)', desc: 'An orchestrator delegates to attack-type specialist agents. Requires an authorized engagement.' },
                        ].map((m) => {
                            const isSel = mode === m.id;
                            return (
                                <div key={m.id} onClick={() => setMode(m.id as 'classic' | 'agentic' | 'deep')}
                                    className={`cursor-pointer p-5 rounded-xl border transition-all duration-200 ${isSel ? 'bg-blue-50 dark:bg-blue-500/5 border-blue-200 dark:border-blue-500/30' : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}`}>
                                    <div className="flex items-start justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <m.icon className={`w-5 h-5 ${isSel ? 'text-blue-600 dark:text-blue-400' : 'text-gray-500'}`} />
                                            <h4 className={`font-medium ${isSel ? 'text-blue-900 dark:text-white' : 'text-gray-700 dark:text-gray-300'}`}>{m.title}</h4>
                                        </div>
                                        <div className={`w-5 h-5 rounded-full flex items-center justify-center border transition-colors ${isSel ? 'bg-blue-600 border-blue-600' : 'border-gray-300 dark:border-gray-700'}`}>
                                            {isSel && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                        </div>
                                    </div>
                                    <p className="text-xs text-gray-500 leading-relaxed">{m.desc}</p>
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* ============ CLASSIC: Scan Phases ============ */}
                {mode === 'classic' && (
                    <>
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center gap-2"><div className="animate-spin-slow"><Search className="w-5 h-5 text-blue-600 dark:text-blue-500" /></div><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Scan Phases</h2></div>
                                <button type="button" onClick={toggleAllPhases}
                                    className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline">
                                    {allPhasesSelected ? 'Clear all' : 'Select all'}
                                </button>
                            </div>
                            <div className="space-y-8">
                                {Object.entries(phases).map(([category, categoryPhases]) => (
                                    <div key={category}>
                                        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4 pl-1">{category}</h3>
                                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                            {categoryPhases.map((phase, index) => {
                                                const isSelected = selectedPhases.includes(phase.id);
                                                return (
                                                    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * 0.1 }}
                                                        key={phase.id} onClick={() => togglePhase(phase.id)}
                                                        className={`cursor-pointer p-5 rounded-xl border transition-all duration-200 group ${isSelected ? 'bg-blue-50 dark:bg-blue-500/5 border-blue-200 dark:border-blue-500/30' : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}`}>
                                                        <div className="flex items-start justify-between mb-3">
                                                            <div>
                                                                <h4 className={`font-medium mb-1 ${isSelected ? 'text-blue-900 dark:text-white' : 'text-gray-700 dark:text-gray-300'}`}>{phase.id}</h4>
                                                                <p className="text-xs text-gray-500 leading-relaxed">{phase.description}</p>
                                                            </div>
                                                            <div className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${isSelected ? 'bg-blue-600 border-blue-600' : 'border-gray-300 dark:border-gray-700 group-hover:border-gray-400 dark:group-hover:border-gray-600'}`}>
                                                                {isSelected && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                                            </div>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2 mt-4">
                                                            {phase.tools.map((tool) => (
                                                                <span key={tool} className={`px-2 py-1 rounded text-[10px] font-mono border ${isSelected ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20' : 'bg-white dark:bg-gray-900 text-gray-500 border-gray-200 dark:border-gray-800'}`}>{tool}</span>
                                                            ))}
                                                        </div>
                                                    </motion.div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                        <div className="bg-blue-50 dark:bg-blue-500/5 border border-blue-100 dark:border-blue-500/10 rounded-xl p-6">
                            <p className="text-sm text-blue-600 dark:text-blue-400">Selected phases: <span className="font-bold text-gray-900 dark:text-white">{selectedPhases.length} of {totalPhases}</span></p>
                            <p className="text-xs text-gray-500 mt-1">Estimated scan duration: 15-25 minutes depending on target size</p>
                        </div>
                    </>
                )}

                {/* ============ AGENTIC: AI-Guided inputs ============ */}
                {mode === 'agentic' && (
                    <>
                        {/* Objective */}
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center gap-2 mb-4"><Bot className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Objective</h2></div>
                            <textarea value={objective} onChange={(e) => setObjective(e.target.value)} rows={2} placeholder="e.g. Discover exposed web services and find exploitable vulnerabilities."
                                className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500" />
                        </div>

                        {/* Scope & limits */}
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm space-y-4">
                            <div className="flex items-center gap-2 mb-2"><Crosshair className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Scope & Limits</h2></div>
                            <div>
                                <label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Exclusions (comma-separated hosts, optional)</label>
                                <input value={exclusions} onChange={(e) => setExclusions(e.target.value)} placeholder="admin.example.com, billing.example.com"
                                    className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500" />
                                <p className="text-xs text-gray-400 mt-1">The target is automatically in-scope. Commands referencing exclusions are blocked.</p>
                            </div>
                            <div className="grid grid-cols-3 gap-4">
                                <div><label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Max commands</label>
                                    <input type="number" value={maxCommands} onChange={(e) => setMaxCommands(e.target.value)} className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg" /></div>
                                <div><label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Max seconds</label>
                                    <input type="number" value={maxSeconds} onChange={(e) => setMaxSeconds(e.target.value)} className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg" /></div>
                                <div><label className="block text-xs font-medium text-gray-500 mb-1 uppercase">Per-cmd timeout</label>
                                    <input type="number" value={perCmdTimeout} onChange={(e) => setPerCmdTimeout(e.target.value)} className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg" /></div>
                            </div>
                        </div>

                        {/* Tools */}
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2"><Wrench className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Tools the agent may use</h2></div>
                                <div className="flex items-center gap-4">
                                    {aiTools.length > 0 && (
                                        <button type="button" onClick={toggleAllTools}
                                            className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline">
                                            {allToolsSelected ? 'Clear all' : 'Select all'}
                                        </button>
                                    )}
                                    <Link to="/ai-tools" className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Manage tools</Link>
                                </div>
                            </div>
                            {aiTools.length === 0 ? (
                                <p className="text-sm text-gray-500">No enabled tools. Go to <Link to="/ai-tools" className="text-blue-600 dark:text-blue-400 hover:underline">AI Tools</Link> and add some (or seed defaults).</p>
                            ) : (
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[19rem] overflow-y-auto custom-scrollbar pr-1">
                                    {aiTools.map((t) => {
                                        const on = selectedToolIds.includes(t.id);
                                        return (
                                            <div key={t.id} onClick={() => toggleTool(t.id)}
                                                className={`cursor-pointer p-4 rounded-xl border transition-all ${on ? 'bg-blue-50 dark:bg-blue-500/5 border-blue-200 dark:border-blue-500/30' : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}`}>
                                                <div className="flex items-center justify-between">
                                                    <span className="font-medium text-gray-900 dark:text-white">{t.name}</span>
                                                    <span className="text-xs font-mono text-blue-600 dark:text-blue-400">{t.binary}</span>
                                                </div>
                                                <p className="text-xs text-gray-500 mt-1 line-clamp-2">{t.description}</p>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* Authorization */}
                        <div className="bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
                            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                            <label className="text-sm text-amber-800 dark:text-amber-300 flex items-start gap-2 cursor-pointer">
                                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" />
                                <span>The AI will author and run real commands against this target. I confirm I am authorized to test it and accept the scope/limits above.</span>
                            </label>
                        </div>
                    </>
                )}

                {/* ============ DEEP AGENT: engagement + specialists ============ */}
                {mode === 'deep' && (
                    <>
                        {/* Authorized engagement */}
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2"><ShieldCheck className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Authorized Engagement</h2></div>
                                <Link to="/engagements" className="text-xs text-blue-600 dark:text-blue-400 hover:underline">Manage engagements</Link>
                            </div>
                            {engagements.length === 0 ? (
                                <p className="text-sm text-gray-500">No active engagements. Create one in <Link to="/engagements" className="text-blue-600 dark:text-blue-400 hover:underline">Engagements</Link> to authorize a target before running a deep scan.</p>
                            ) : (
                                <select value={engagementId ?? ''} onChange={(e) => setEngagementId(Number(e.target.value))}
                                    className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-3 py-2 rounded-lg focus:outline-none focus:border-blue-500">
                                    {engagements.map((e) => (
                                        <option key={e.id} value={e.id}>{e.org} — scope: {e.inScope.join(', ')}</option>
                                    ))}
                                </select>
                            )}
                            <p className="text-xs text-gray-400 mt-2">The target must fall within the selected engagement's in-scope list, or the scan is refused.</p>
                        </div>

                        {/* Specialists */}
                        <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-2"><Bot className="w-5 h-5 text-blue-600 dark:text-blue-500" /><h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Specialist Agents</h2></div>
                                <button type="button" onClick={toggleAllSpecialists} className="text-xs font-medium text-blue-600 dark:text-blue-400 hover:underline">
                                    {allSpecialistsSelected ? 'Clear all' : 'Select all'}
                                </button>
                            </div>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {DEEP_SPECIALISTS.map((s) => {
                                    const on = selectedSpecialists.includes(s.key);
                                    return (
                                        <div key={s.key} onClick={() => toggleSpecialist(s.key)}
                                            className={`cursor-pointer p-4 rounded-xl border transition-all ${on ? 'bg-blue-50 dark:bg-blue-500/5 border-blue-200 dark:border-blue-500/30' : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}`}>
                                            <div className="flex items-start justify-between">
                                                <span className="font-medium text-gray-900 dark:text-white">{s.name}</span>
                                                <div className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${on ? 'bg-blue-600 border-blue-600' : 'border-gray-300 dark:border-gray-700'}`}>
                                                    {on && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                                </div>
                                            </div>
                                            <p className="text-xs text-gray-500 mt-1">{s.desc}</p>
                                        </div>
                                    );
                                })}
                            </div>
                            <p className="text-xs text-gray-400 mt-3">Selected: <span className="font-bold text-gray-900 dark:text-white">{selectedSpecialists.length} of {DEEP_SPECIALISTS.length}</span>. The orchestrator runs Recon first, then the others.</p>
                        </div>

                        {/* Authorization */}
                        <div className="bg-amber-50 dark:bg-amber-500/5 border border-amber-200 dark:border-amber-500/20 rounded-xl p-4 flex items-start gap-3">
                            <ShieldAlert className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                            <label className="text-sm text-amber-800 dark:text-amber-300 flex items-start gap-2 cursor-pointer">
                                <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} className="mt-1" />
                                <span>The specialist agents will run real commands against this target. I confirm this target is authorized under the selected engagement and accept that DoS is assessed non-destructively only.</span>
                            </label>
                        </div>
                    </>
                )}
            </div>
        </PageTransition>
    );
};

export default NewScan;
