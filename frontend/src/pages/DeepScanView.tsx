import { useState, useEffect, useCallback, useMemo, useRef, Suspense } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Text, Billboard, Line, Stars } from '@react-three/drei';
import * as THREE from 'three';
import { ArrowLeft, Square, Download, Cpu, Terminal, X, Loader2, ChevronRight } from 'lucide-react';
import api from '../api/axios';
import { useSSE } from '../context/SSEContext';

// Exact backend specialist display names (services/deep_agent/specialists.py).
const SPECIALIST_META: Record<string, { key: string; short: string; color: string }> = {
    'Recon & Asset Discovery Specialist': { key: 'recon', short: 'Recon', color: '#38bdf8' },
    'Network & Port Specialist': { key: 'nmap', short: 'Nmap', color: '#22d3ee' },
    'SQL Injection Specialist': { key: 'sqli', short: 'SQLi', color: '#f472b6' },
    'XSS Specialist': { key: 'xss', short: 'XSS', color: '#fb923c' },
    'CVE & Misconfiguration Specialist': { key: 'nuclei', short: 'CVE/Nuclei', color: '#a78bfa' },
    'Content Discovery Specialist': { key: 'fuzzing', short: 'FFUF', color: '#34d399' },
    'DoS-Resilience Specialist': { key: 'dos', short: 'DoS', color: '#f59e0b' },
    'Web-Logic Flaw Specialist': { key: 'weblogic', short: 'Web-Logic', color: '#e879f9' },
    'Credential Specialist': { key: 'bruteforce', short: 'Brute-Force', color: '#f87171' },
    'TLS / WAF / Headers Specialist': { key: 'tls', short: 'TLS/WAF', color: '#60a5fa' },
};
const KEY_TO_NAME: Record<string, string> = Object.fromEntries(
    Object.entries(SPECIALIST_META).map(([name, m]) => [m.key, name])
);

type Status = 'idle' | 'running' | 'done' | 'failed';
const STATUS_COLOR: Record<Status, string> = { idle: '#64748b', running: '#22d3ee', done: '#22c55e', failed: '#ef4444' };

interface Spec { name: string; short: string; color: string; status: Status; pos: [number, number, number]; }

// ----------------------------- 3D primitives ----------------------------- //

function Core({ thinking }: { thinking: boolean }) {
    const core = useRef<THREE.Mesh>(null);
    const halo = useRef<THREE.Mesh>(null);
    useFrame((s) => {
        const t = s.clock.elapsedTime;
        if (core.current) {
            core.current.rotation.y = t * 0.3;
            core.current.rotation.x = t * 0.12;
            const m = core.current.material as THREE.MeshStandardMaterial;
            m.emissiveIntensity = thinking ? 1.2 + Math.sin(t * 3) * 0.6 : 0.5;
        }
        if (halo.current) {
            const p = thinking ? 1 + Math.sin(t * 3) * 0.12 : 1;
            halo.current.scale.setScalar(1.65 * p);
        }
    });
    return (
        <group>
            <mesh ref={core}>
                <icosahedronGeometry args={[1.1, 1]} />
                <meshStandardMaterial color="#22d3ee" emissive="#06b6d4" emissiveIntensity={0.6} roughness={0.2} metalness={0.6} flatShading />
            </mesh>
            <mesh ref={halo}>
                <sphereGeometry args={[1.1, 32, 32]} />
                <meshBasicMaterial color="#22d3ee" transparent opacity={0.07} />
            </mesh>
            <Billboard position={[0, 2, 0]}>
                <Text fontSize={0.42} color="#e2e8f0" anchorX="center" anchorY="middle" outlineWidth={0.01} outlineColor="#0b1220">
                    ORCHESTRATOR
                </Text>
            </Billboard>
        </group>
    );
}

function Beam({ to, color, active }: { to: [number, number, number]; color: string; active: boolean }) {
    const packet = useRef<THREE.Mesh>(null);
    const a = useMemo(() => new THREE.Vector3(0, 0, 0), []);
    const b = useMemo(() => new THREE.Vector3(...to), [to]);
    useFrame((s) => {
        if (active && packet.current) {
            const t = (s.clock.elapsedTime * 0.55) % 1;
            packet.current.position.lerpVectors(a, b, t);
        }
    });
    return (
        <group>
            <Line points={[[0, 0, 0], to]} color={active ? color : '#334155'} lineWidth={active ? 2.5 : 1} transparent opacity={active ? 0.9 : 0.22} />
            {active && (
                <mesh ref={packet}>
                    <sphereGeometry args={[0.13, 12, 12]} />
                    <meshBasicMaterial color={color} />
                </mesh>
            )}
        </group>
    );
}

function SpecialistNode({ spec, selected, onSelect }: { spec: Spec; selected: boolean; onSelect: (n: string) => void }) {
    const mesh = useRef<THREE.Mesh>(null);
    const ring = useRef<THREE.Mesh>(null);
    const [hover, setHover] = useState(false);
    // Always render in the specialist's own colour (so every node stays visible and
    // identifiable on the dark background); only a failure tints the node red. Status
    // otherwise reads from the label, the pulse, and the lit beam.
    const base = spec.status === 'failed' ? '#ef4444' : spec.color;
    useFrame((s) => {
        const t = s.clock.elapsedTime;
        if (mesh.current) {
            const pulse = spec.status === 'running' ? 1 + Math.sin(t * 5) * 0.14 : hover ? 1.12 : 1;
            mesh.current.scale.setScalar(pulse);
            mesh.current.rotation.y = t * 0.4;
            const m = mesh.current.material as THREE.MeshStandardMaterial;
            m.emissiveIntensity = spec.status === 'running'
                ? 1.0 + Math.sin(t * 5) * 0.4
                : spec.status === 'idle' ? 0.6 : 0.85;
        }
        if (ring.current) ring.current.rotation.z = t * 0.8;
    });
    return (
        <group position={spec.pos}>
            <mesh
                ref={mesh}
                onClick={(e) => { e.stopPropagation(); onSelect(spec.name); }}
                onPointerOver={(e) => { e.stopPropagation(); setHover(true); document.body.style.cursor = 'pointer'; }}
                onPointerOut={() => { setHover(false); document.body.style.cursor = 'auto'; }}
            >
                <icosahedronGeometry args={[0.72, 0]} />
                <meshStandardMaterial color={base} emissive={base} emissiveIntensity={0.6} roughness={0.35} metalness={0.25} flatShading />
            </mesh>
            {selected && (
                <mesh ref={ring} rotation={[Math.PI / 2, 0, 0]}>
                    <torusGeometry args={[1.0, 0.045, 8, 48]} />
                    <meshBasicMaterial color="#e2e8f0" />
                </mesh>
            )}
            <Billboard position={[0, 1.15, 0]}>
                <Text fontSize={0.34} color="#f1f5f9" anchorX="center" anchorY="middle" outlineWidth={0.012} outlineColor="#0b1220">
                    {spec.short}
                </Text>
                <Text position={[0, -0.34, 0]} fontSize={0.2} color={STATUS_COLOR[spec.status]} anchorX="center" anchorY="middle">
                    {spec.status === 'running' ? '● working' : spec.status}
                </Text>
            </Billboard>
        </group>
    );
}

function Scene({ specs, activeName, selectedName, onSelect, thinking }:
    { specs: Spec[]; activeName: string | null; selectedName: string | null; onSelect: (n: string) => void; thinking: boolean }) {
    return (
        <>
            <ambientLight intensity={0.9} />
            <hemisphereLight args={['#bcd7ff', '#1a2740', 0.6]} />
            <pointLight position={[0, 0, 0]} intensity={2.6} color="#22d3ee" distance={40} />
            <directionalLight position={[8, 12, 10]} intensity={0.7} />
            <Stars radius={80} depth={45} count={1400} factor={3.2} fade speed={0.4} />
            <Core thinking={thinking} />
            {specs.map((s) => <Beam key={'beam-' + s.name} to={s.pos} color={s.color} active={s.name === activeName} />)}
            {specs.map((s) => <SpecialistNode key={s.name} spec={s} selected={s.name === selectedName} onSelect={onSelect} />)}
            <OrbitControls enablePan={false} autoRotate autoRotateSpeed={0.5} minDistance={9} maxDistance={40} />
        </>
    );
}

// ----------------------------- Page ----------------------------- //

const DeepScanView = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const { addEventListener, removeEventListener } = useSSE();
    const [scan, setScan] = useState<any>(null);
    const [results, setResults] = useState<any[]>([]);
    const [decisions, setDecisions] = useState<any[]>([]);
    const [selectedName, setSelectedName] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const orchLogRef = useRef<HTMLDivElement>(null);

    const fetchAll = useCallback(async () => {
        try {
            const [s, d] = await Promise.all([
                api.get(`/scans/${id}`),
                api.get(`/ctem/scans/${id}/agent-decisions`),
            ]);
            setScan(s.data);
            setResults(Array.isArray(s.data?.results) ? s.data.results : []);
            setDecisions(Array.isArray(d.data) ? d.data : []);
        } catch (e) {
            console.error('fetch deep scan failed', e);
        } finally {
            setLoading(false);
        }
    }, [id]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    // Live refetch on any SCAN_UPDATE for this scan.
    useEffect(() => {
        const onUpdate = (data: any) => {
            if (data && Number(data.scanId) === Number(id)) fetchAll();
        };
        addEventListener('SCAN_UPDATE', onUpdate);
        return () => removeEventListener('SCAN_UPDATE', onUpdate);
    }, [id, addEventListener, removeEventListener, fetchAll]);

    // Fallback poll while running.
    useEffect(() => {
        if (scan?.status !== 'Running') return;
        const t = setInterval(fetchAll, 2500);
        return () => clearInterval(t);
    }, [scan?.status, fetchAll]);

    const running = scan?.status === 'Running';

    const statusFor = useCallback((name: string): Status => {
        const rs = results.filter((r) => r.phase === name);
        if (rs.some((r) => r.status === 'Running' || r.status === 'Pending')) return 'running';
        if (rs.length === 0) return 'idle';
        if (rs.some((r) => r.status === 'Completed')) return 'done';
        if (rs.every((r) => r.status === 'Failed' || r.status === 'Skipped')) return 'failed';
        return 'done';
    }, [results]);

    // Specialists deployed: from scan.selectedSpecialists (keys) + any seen in results.
    const specs: Spec[] = useMemo(() => {
        const names: string[] = [];
        const seen = new Set<string>();
        try {
            const keys: string[] = JSON.parse(scan?.selectedSpecialists || '[]');
            keys.forEach((k) => { const n = KEY_TO_NAME[k]; if (n && !seen.has(n)) { names.push(n); seen.add(n); } });
        } catch { /* ignore */ }
        results.forEach((r) => { if (r.phase && SPECIALIST_META[r.phase] && !seen.has(r.phase)) { names.push(r.phase); seen.add(r.phase); } });
        const n = Math.max(1, names.length);
        // Wider orbit + 4 staggered heights so labels never collide in projection.
        const R = 9.5;
        const yLevels = [-2.4, -0.8, 0.8, 2.4];
        return names.map((name, i) => {
            const ang = (i / n) * Math.PI * 2;
            const meta = SPECIALIST_META[name];
            return {
                name, short: meta.short, color: meta.color, status: statusFor(name),
                pos: [Math.cos(ang) * R, yLevels[i % yLevels.length], Math.sin(ang) * R] as [number, number, number],
            };
        });
    }, [scan, results, statusFor]);

    // Orchestrator narration steps (modelUsed='orchestrator').
    const orchSteps = useMemo(
        () => decisions.filter((d) => d.modelUsed === 'orchestrator' || d.ctemStage === 'Orchestrator'),
        [decisions]
    );
    const lastDelegate = useMemo(() => {
        for (let i = orchSteps.length - 1; i >= 0; i--) {
            try { const t = JSON.parse(orchSteps[i].selectedTools || '[]'); if (t[0]) return t[0] as string; } catch { /* */ }
        }
        return null;
    }, [orchSteps]);

    const runningSpec = specs.find((s) => s.status === 'running');
    const activeName = runningSpec?.name || (running ? lastDelegate : null);

    useEffect(() => {
        if (orchLogRef.current) orchLogRef.current.scrollTop = orchLogRef.current.scrollHeight;
    }, [orchSteps.length]);

    const stop = async () => { try { await api.post(`/scans/${id}/stop`); fetchAll(); } catch { /* */ } };

    const selectedResults = selectedName ? results.filter((r) => r.phase === selectedName).sort((a, b) => a.id - b.id) : [];
    const delegateName = (raw: string | null) => (raw && SPECIALIST_META[raw] ? SPECIALIST_META[raw].short : raw);

    const statusBadge = () => {
        const map: Record<string, string> = {
            Running: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
            Completed: 'bg-green-500/15 text-green-300 border-green-500/30',
            Failed: 'bg-red-500/15 text-red-300 border-red-500/30',
            Stopped: 'bg-gray-500/15 text-gray-300 border-gray-500/30',
        };
        return map[scan?.status] || 'bg-gray-500/15 text-gray-300 border-gray-500/30';
    };

    return (
        <div className="relative w-full h-[calc(100vh-4rem)] min-h-[560px] rounded-2xl overflow-hidden bg-[#070b14]">
            {/* 3D canvas */}
            <Canvas camera={{ position: [0, 6, 22], fov: 52 }} dpr={[1, 2]}>
                <color attach="background" args={['#070b14']} />
                <fog attach="fog" args={['#070b14', 22, 48]} />
                <Suspense fallback={null}>
                    <Scene specs={specs} activeName={activeName} selectedName={selectedName} onSelect={setSelectedName} thinking={running} />
                </Suspense>
            </Canvas>

            {/* ---------- Overlay UI ---------- */}
            <div className="absolute inset-0 pointer-events-none">
                {/* Top bar */}
                <div className="absolute top-0 left-0 right-0 flex items-center justify-between px-5 py-3 bg-gradient-to-b from-black/60 to-transparent pointer-events-auto">
                    <div className="flex items-center gap-3">
                        <button onClick={() => navigate(-1)} className="p-2 rounded-lg hover:bg-white/10 text-gray-300">
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                        <div>
                            <div className="flex items-center gap-2">
                                <span className="text-lg font-bold text-white">{scan?.target || '…'}</span>
                                <span className={`px-2 py-0.5 text-[11px] rounded-full border ${statusBadge()}`}>{scan?.status || '…'}</span>
                            </div>
                            <p className="text-xs text-gray-400">Deep Agent · orchestrator &amp; {specs.length} specialist{specs.length === 1 ? '' : 's'}</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        {running && (
                            <button onClick={stop} className="px-3 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium flex items-center gap-2">
                                <Square className="w-4 h-4 fill-current" /> Stop
                            </button>
                        )}
                        {scan?.pdfPath && scan?.status === 'Completed' && (
                            <a href={`/${scan.pdfPath}`} target="_blank" rel="noreferrer"
                                className="px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium flex items-center gap-2">
                                <Download className="w-4 h-4" /> Report
                            </a>
                        )}
                    </div>
                </div>

                {loading && (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-300">
                        <Loader2 className="w-6 h-6 animate-spin" />
                    </div>
                )}

                {/* Orchestrator log (bottom-left) */}
                <div className="absolute bottom-4 left-4 w-[340px] max-w-[42vw] bg-[#0b1322]/85 backdrop-blur border border-cyan-500/20 rounded-xl p-3 pointer-events-auto">
                    <div className="flex items-center gap-2 mb-2 text-cyan-300">
                        <Cpu className="w-4 h-4" />
                        <span className="text-xs font-semibold uppercase tracking-wider">Orchestrator</span>
                        {running && <span className="text-[10px] text-cyan-400/80 animate-pulse">thinking…</span>}
                    </div>
                    <div ref={orchLogRef} className="space-y-2 max-h-44 overflow-y-auto custom-scrollbar pr-1">
                        {orchSteps.length === 0 ? (
                            <p className="text-xs text-gray-500">Waiting for the orchestrator to plan…</p>
                        ) : orchSteps.map((d, i) => {
                            let deleg: string | null = null;
                            try { deleg = JSON.parse(d.selectedTools || '[]')[0] || null; } catch { /* */ }
                            return (
                                <div key={d.id || i} className="text-xs text-gray-300 border-l-2 border-cyan-500/30 pl-2">
                                    {d.reasoning && <p className="leading-snug">{d.reasoning}</p>}
                                    {deleg && (
                                        <p className="mt-0.5 text-cyan-400 flex items-center gap-1">
                                            <ChevronRight className="w-3 h-3" /> delegating to <span className="font-semibold">{delegateName(deleg)}</span>
                                        </p>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>

                {/* Legend (bottom-right when no panel) */}
                {!selectedName && (
                    <div className="absolute bottom-4 right-4 bg-[#0b1322]/80 backdrop-blur border border-white/10 rounded-xl px-3 py-2 text-[11px] text-gray-400 pointer-events-auto">
                        <p className="mb-1 font-medium text-gray-300">Click a specialist to inspect</p>
                        <div className="flex items-center gap-3">
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.running }} /> working</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.done }} /> done</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.failed }} /> failed</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{ background: STATUS_COLOR.idle }} /> idle</span>
                        </div>
                    </div>
                )}

                {/* Specialist inspect panel (right) */}
                {selectedName && (
                    <div className="absolute top-16 right-4 bottom-4 w-[420px] max-w-[46vw] bg-[#0b1322]/92 backdrop-blur border border-white/10 rounded-xl flex flex-col pointer-events-auto">
                        <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
                            <div className="flex items-center gap-2">
                                <span className="w-3 h-3 rounded-full" style={{ background: SPECIALIST_META[selectedName]?.color }} />
                                <span className="font-semibold text-white text-sm">{selectedName}</span>
                            </div>
                            <button onClick={() => setSelectedName(null)} className="p-1 rounded hover:bg-white/10 text-gray-400"><X className="w-4 h-4" /></button>
                        </div>
                        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-3">
                            {selectedResults.length === 0 ? (
                                <p className="text-sm text-gray-500">This specialist hasn't run any commands yet.</p>
                            ) : selectedResults.map((r) => (
                                <div key={r.id} className="border border-white/10 rounded-lg overflow-hidden">
                                    <div className="flex items-center justify-between px-3 py-2 bg-white/5">
                                        <span className="flex items-center gap-2 text-xs font-medium text-gray-200">
                                            <Terminal className="w-3.5 h-3.5 text-cyan-400" /> {r.tool}
                                        </span>
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full ${r.status === 'Completed' ? 'bg-green-500/15 text-green-300' : r.status === 'Running' ? 'bg-cyan-500/15 text-cyan-300' : r.status === 'Failed' ? 'bg-red-500/15 text-red-300' : 'bg-gray-500/15 text-gray-300'}`}>
                                            {r.status}{r.exit_code != null ? ` · exit ${r.exit_code}` : ''}
                                        </span>
                                    </div>
                                    {r.command && <div className="px-3 py-1.5 font-mono text-[11px] text-cyan-300/90 break-all border-b border-white/5">$ {r.command}</div>}
                                    <pre className="px-3 py-2 text-[11px] text-gray-300 whitespace-pre-wrap break-words max-h-56 overflow-y-auto custom-scrollbar font-mono">
                                        {(r.raw_output || '').slice(0, 6000) || '(no output)'}
                                    </pre>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default DeepScanView;
