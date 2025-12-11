import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import { 
    ArrowLeft, Download, Shield, AlertTriangle, CheckCircle, 
    Clock, FileText, Terminal, Activity, Globe, Copy, Square,
    Server, MapPin, Database, Bot 
} from 'lucide-react';
import api from '../api/axios';
import WebIntelligence from '../components/WebIntelligence';
import Modal from '../components/Modal';

const containerVariants = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: {
            staggerChildren: 0.05
        }
    }
};

const itemVariants = {
    hidden: { opacity: 0, y: 10 },
    show: { opacity: 1, y: 0 }
};

const slideVariants = {
    enter: (direction: number) => ({
        x: direction > 0 ? 20 : -20,
        opacity: 0
    }),
    center: {
        zIndex: 1,
        x: 0,
        opacity: 1
    },
    exit: (direction: number) => ({
        zIndex: 0,
        x: direction < 0 ? 20 : -20,
        opacity: 0
    })
};

const ScanDetails = () => {
    const { id } = useParams();
    const navigate = useNavigate();
    const [scan, setScan] = useState<any>(null);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState('summary');
    const [direction, setDirection] = useState(0);

    const tabOrder = ['summary', 'findings', 'web-intel', 'logs', 'report'];

    const handleTabChange = (newTab: string) => {
        const oldIndex = tabOrder.indexOf(activeTab);
        const newIndex = tabOrder.indexOf(newTab);
        setDirection(newIndex > oldIndex ? 1 : -1);
        setActiveTab(newTab);
    };
    const [severityFilter, setSeverityFilter] = useState('All');
    const [expandedFinding, setExpandedFinding] = useState<number | null>(null);
    const [selectedFinding, setSelectedFinding] = useState<any>(null);
    const [isStopping, setIsStopping] = useState(false);

    const handleCreateTicket = (finding: any) => {
        const ticketBody = `
**Vulnerability:** ${finding.Name}
**Severity:** ${finding.Severity}
**CWE:** ${finding.CWE || 'N/A'}

**Description:**
${finding.Description}

**Remediation:**
${finding.Remediation || finding.Mitigation || 'N/A'}

**Evidence:**
${finding.Evidence || 'N/A'}
        `.trim();

        navigator.clipboard.writeText(ticketBody);
        alert('Ticket details copied to clipboard!');
    };

    useEffect(() => {
        const fetchScan = async () => {
            try {
                const response = await api.get(`/scans/${id}`);
                setScan(response.data);
            } catch (error) {
                console.error('Failed to fetch scan details:', error);
            } finally {
                setLoading(false);
            }
        };

        fetchScan();
        
        // Poll for updates if scan is running (Every 5 seconds as requested)
        const interval = setInterval(() => {
            if (scan && scan.status === 'Running') {
                fetchScan();
            }
        }, 5000);

        return () => clearInterval(interval);
    }, [id, scan?.status]);

    const handleStop = async () => {
        if (window.confirm('Are you sure you want to stop this scan?')) {
            setIsStopping(true);
            try {
                await api.post(`/scans/${id}/stop`);
                // Status update will happen via polling
            } catch (error) {
                console.error('Failed to stop scan:', error);
                alert('Failed to stop scan');
                setIsStopping(false);
            }
        }
    };

    // Parse phases safely - Moved up to avoid Hook rule violation
    const phases = React.useMemo(() => {
        if (!scan?.phases) return [];
        if (Array.isArray(scan.phases)) return scan.phases;
        if (typeof scan.phases === 'string') {
            try {
                // Try JSON parse first (replacing single quotes with double if needed)
                return JSON.parse(scan.phases.replace(/'/g, '"'));
            } catch (e) {
                // Fallback: simple split for Python list string representation
                return scan.phases.replace(/[\[\]]/g, '').split(',').map((s: string) => s.trim().replace(/^['"]|['"]$/g, ''));
            }
        }
        return [];
    }, [scan]);

    // Process findings from all scan results - Moved up to be available in scope
    const allFindings = React.useMemo(() => {
        const findings = scan?.results?.flatMap((result: any) => {
            try {
                const parsed = JSON.parse(result.gemini_summary || '{}');
                return (parsed.vulnerabilities || []).map((v: any) => ({
                    ...v,
                    tool: v.Tool || result.tool,
                    timestamp: result.createdAt
                }));
            } catch (e) {
                return [];
            }
        }) || [];
        console.log(findings);

        // Sort by severity
        const severityOrder: { [key: string]: number } = {
            'critical': 0,
            'high': 1,
            'medium': 2,
            'low': 3,
            'info': 4
        };

        return findings.sort((a: any, b: any) => {
            const orderA = severityOrder[a.Severity?.toLowerCase()] ?? 99;
            const orderB = severityOrder[b.Severity?.toLowerCase()] ?? 99;
            return orderA - orderB;
        });
    }, [scan]);

    // Filter findings based on selected severity
    const filteredFindings = React.useMemo(() => {
        if (severityFilter === 'All') return allFindings;
        return allFindings.filter((f: any) => f.Severity === severityFilter);
    }, [allFindings, severityFilter]);

    // Calculate detailed progress metrics
    const progressMetrics = React.useMemo(() => {
        if (!scan?.results || !phases.length) return {
            total: 0, completed: 0, percent: 0,
            currentPhase: 'Initializing...', currentTool: null,
            phaseProgress: {}
        };

        const results = scan.results || [];
        
        // Filter out AI_PHASE_SUMMARY for counting purposes
        const countableResults = results.filter((r: any) => r.tool !== 'AI_PHASE_SUMMARY');
        
        const total = countableResults.length;
        const completed = countableResults.filter((r: any) => r.status === 'Completed').length;
        const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

        const runningTool = results.find((r: any) => r.status === 'Running');
        const pendingTool = results.find((r: any) => r.status === 'Pending');
        const currentTool = runningTool || pendingTool;
        
        const currentPhase = currentTool?.parent_phase_id || currentTool?.phase || (completed === total ? 'Completed' : 'Initializing...');

        // Phase progress
        const phaseProgress: any = {};
        phases.forEach((phase: string) => {
            const phaseTools = results.filter((r: any) => r.parent_phase_id === phase || r.phase === phase);
            // Only count non-AI tools
            const countablePhaseTools = phaseTools.filter((r: any) => r.tool !== 'AI_PHASE_SUMMARY');
            
            phaseProgress[phase] = {
                total: countablePhaseTools.length,
                completed: countablePhaseTools.filter((r: any) => r.status === 'Completed').length,
                failed: countablePhaseTools.filter((r: any) => r.status === 'Failed').length,
                running: phaseTools.filter((r: any) => r.status === 'Running').length // Keep running status even if AI
            };
        });

        return {
            total, completed, percent,
            currentPhase, currentTool,
            phaseProgress
        };
    }, [scan, phases]);

    const [elapsedTime, setElapsedTime] = useState(0);

    useEffect(() => {
        let timerInterval: any;
        if (scan?.status === 'Running' && progressMetrics.currentTool) {
            const startTime = new Date(progressMetrics.currentTool.started_at || progressMetrics.currentTool.createdAt).getTime();
            
            // Update immediately
            setElapsedTime(Math.max(0, Math.round((Date.now() - startTime) / 1000)));

            timerInterval = setInterval(() => {
                setElapsedTime(Math.max(0, Math.round((Date.now() - startTime) / 1000)));
            }, 1000);
        } else {
            setElapsedTime(0);
        }

        return () => {
            if (timerInterval) clearInterval(timerInterval);
        };
    }, [scan?.status, progressMetrics.currentTool]);

    if (loading) return (
        <div className="flex items-center justify-center h-64">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
    );
    
    if (!scan) return <div className="text-white p-8">Scan not found</div>;

    const severityCounts = {
        Critical: allFindings.filter((f: any) => f.Severity === 'Critical').length,
        High: allFindings.filter((f: any) => f.Severity === 'High').length,
        Medium: allFindings.filter((f: any) => f.Severity === 'Medium').length,
        Low: allFindings.filter((f: any) => f.Severity === 'Low').length,
        Info: allFindings.filter((f: any) => f.Severity === 'Info').length,
    };

    // Total for chart (excluding Info)
    const chartTotal = severityCounts.Critical + severityCounts.High + severityCounts.Medium + severityCounts.Low;
    const highSeverityCount = severityCounts.Critical + severityCounts.High;
    
    // Calculate Risk Score (Weighted Average: Critical=100, High=75, Medium=50, Low=25)
    const totalWeightedScore = (severityCounts.Critical * 100) + (severityCounts.High * 75) + (severityCounts.Medium * 50) + (severityCounts.Low * 25);
    const riskScore = chartTotal > 0 ? totalWeightedScore / chartTotal : 0;

    // Donut Chart Component
    const DonutChart = () => {
        const radius = 35; // Slightly smaller radius to accommodate thicker stroke
        const strokeWidth = 20; // Thicker stroke
        const circumference = 2 * Math.PI * radius;
        let currentOffset = 0;
        
        const segments = [
            { count: severityCounts.Critical, color: '#EF4444' }, // Red
            { count: severityCounts.High, color: '#F97316' },     // Orange
            { count: severityCounts.Medium, color: '#EAB308' },   // Yellow
            { count: severityCounts.Low, color: '#3B82F6' },      // Blue
        ].filter(s => s.count > 0);

        if (chartTotal === 0) return (
            <div className="relative w-32 h-32 flex items-center justify-center">
                <div className="w-24 h-24 rounded-full border-4 border-gray-800 flex items-center justify-center text-gray-600 text-xs font-medium">
                    No Issues
                </div>
            </div>
        );

        return (
            <div className="relative w-32 h-32">
                <div className="absolute inset-0 flex items-center justify-center z-10 flex-col">
                    <span className="text-2xl font-bold text-gray-900 dark:text-white leading-none">{chartTotal}</span>
                    <span className="text-[10px] text-gray-500 uppercase font-medium mt-1">Issues</span>
                </div>
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                    {/* Background Circle */}
                    <circle
                        cx="50"
                        cy="50"
                        r={radius}
                        fill="transparent"
                        className="stroke-gray-100 dark:stroke-gray-800"
                        strokeWidth={strokeWidth}
                    />
                    {segments.map((segment, i) => {
                        const percentage = segment.count / chartTotal;
                        const dashArray = percentage * circumference;
                        const offset = currentOffset;
                        currentOffset -= dashArray;
                        
                        return (
                            <circle
                                key={i}
                                cx="50"
                                cy="50"
                                r={radius}
                                fill="transparent"
                                stroke={segment.color}
                                strokeWidth={strokeWidth}
                                strokeDasharray={`${dashArray} ${circumference}`}
                                strokeDashoffset={offset}
                                strokeLinecap="butt" // Changed to butt to match the clean look, or round if gaps needed
                                className="transition-all duration-1000 ease-out"
                            />
                        );
                    })}
                </svg>
            </div>
        );
    };



    return (
        <PageTransition className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <button 
                        onClick={() => navigate('/scan/history')}
                        className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                    >
                        <ArrowLeft className="w-5 h-5" />
                    </button>
                    <div>
                        <div className="flex items-center gap-3">
                            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{scan.target}</h1>
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                                scan.status === 'Completed' ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-500 border-green-200 dark:border-green-500/20' :
                                scan.status === 'Failed' ? 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-500 border-red-200 dark:border-red-500/20' :
                                scan.status === 'Stopped' ? 'bg-yellow-100 dark:bg-yellow-500/10 text-yellow-700 dark:text-yellow-500 border-yellow-200 dark:border-yellow-500/20' :
                                'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-500 border-blue-200 dark:border-blue-500/20'
                            }`}>
                                {scan.status}
                            </span>
                        </div>
                        <p className="text-sm text-gray-500 mt-1">Scan #{scan.scan_number}</p>
                    </div>
                </div>
                
                <div className="flex items-center gap-3">
                    {scan.status === 'Running' && (
                        <button 
                            onClick={handleStop}
                            disabled={isStopping}
                            className={`flex items-center gap-2 px-4 py-2 rounded-lg border transition-colors ${
                                isStopping 
                                ? 'bg-gray-100 dark:bg-gray-800 text-gray-500 border-gray-200 dark:border-gray-700 cursor-not-allowed' 
                                : 'bg-red-50 dark:bg-red-500/10 hover:bg-red-100 dark:hover:bg-red-500/20 text-red-600 dark:text-red-500 border-red-200 dark:border-red-500/20'
                            }`}
                        >
                            {isStopping ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                                    Stopping...
                                </>
                            ) : (
                                <>
                                    <Square className="w-4 h-4 fill-current" />
                                    Stop Scan
                                </>
                            )}
                        </button>
                    )}
                    
                    {scan.pdfPath && (
                        <button 
                            onClick={() => {
                                const filename = scan.pdfPath.split(/[/\\]/).pop();
                                const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
                                const cleanBaseUrl = baseUrl.replace(/\/$/, '');
                                window.open(`${cleanBaseUrl}/reports/${filename}`, '_blank');
                            }}
                            className="flex items-center gap-2 px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-white rounded-lg border border-gray-200 dark:border-gray-700 transition-colors shadow-sm"
                        >
                            <Download className="w-4 h-4" />
                            Download PDF
                        </button>
                    )}
                </div>
            </div>



            {/* Stats Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {/* Vulnerability Distribution */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 flex flex-col justify-between h-full shadow-sm">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="text-gray-900 dark:text-white text-lg font-bold mb-6">Vulnerability Distribution</h3>
                        <div className="px-3 py-1 rounded-lg bg-gray-100 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 text-xs font-medium">
                            Total: <span className="text-gray-900 dark:text-white font-bold">{chartTotal}</span>
                        </div>
                    </div>

                    <div className="flex items-center gap-8 mb-8">
                        {/* Chart - Left */}
                        <div className="flex-shrink-0">
                            <DonutChart />
                        </div>

                        {/* Legend - Right */}
                        <div className="flex-1 space-y-3">
                            {[
                                { label: 'Critical', count: severityCounts.Critical, color: 'bg-red-500', text: 'text-red-500' },
                                { label: 'High', count: severityCounts.High, color: 'bg-orange-500', text: 'text-orange-500' },
                                { label: 'Medium', count: severityCounts.Medium, color: 'bg-yellow-500', text: 'text-yellow-500' },
                                { label: 'Low', count: severityCounts.Low, color: 'bg-blue-500', text: 'text-blue-500' }
                            ].map((item) => (
                                <div key={item.label} className="flex items-center justify-between text-sm">
                                    <div className="flex items-center gap-2">
                                        <div className={`w-2.5 h-2.5 rounded-full ${item.color}`}></div>
                                        <span className="text-gray-500 dark:text-gray-300">{item.label}</span>
                                    </div>
                                    <div className="flex items-center gap-4">
                                        <span className={`${item.count > 0 ? item.text : 'text-gray-400 dark:text-gray-500'} font-medium`}>{item.count}</span>
                                        <span className="text-gray-500 dark:text-gray-600 w-12 text-right">
                                            {chartTotal > 0 ? ((item.count / chartTotal) * 100).toFixed(1) : '0.0'}%
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Footer Stats */}
                    <div className="grid grid-cols-2 gap-4 pt-6 border-t border-gray-200 dark:border-gray-800">
                        <div>
                            <p className="text-xs text-gray-500 uppercase font-medium mb-1">High Priority</p>
                            <p className={`text-2xl font-bold ${highSeverityCount > 0 ? 'text-orange-500' : 'text-gray-400 dark:text-gray-600'}`}>
                                {highSeverityCount}
                            </p>
                        </div>
                        <div>
                            <p className="text-xs text-gray-500 uppercase font-medium mb-1">Risk Score</p>
                            <div className="flex items-baseline gap-1">
                                <p className={`text-2xl font-bold ${
                                    riskScore >= 75 ? 'text-red-500' :
                                    riskScore >= 50 ? 'text-orange-500' :
                                    riskScore >= 25 ? 'text-yellow-500' :
                                    'text-blue-500'
                                }`}>
                                    {riskScore.toFixed(1)}
                                </p>
                                <span className="text-sm text-gray-400 dark:text-gray-500">/100</span>
                            </div>
                        </div>
                    </div>
                </div>
                
                {/* Target Intelligence */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 relative overflow-hidden shadow-sm">
                    <div className="absolute top-6 right-6 w-2 h-2 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]"></div>
                    <h3 className="text-gray-900 dark:text-white text-lg font-bold mb-6">Target Intelligence</h3>
                    
                    <div className="space-y-6">
                        {/* Domain Info */}
                        <div className="flex items-start gap-4">
                            <div className="p-3 bg-blue-500/10 rounded-xl">
                                <Globe className="w-6 h-6 text-blue-500" />
                            </div>
                            <div>
                                <p className="text-xs text-gray-500 uppercase font-medium mb-1">Domain</p>
                                <p className="text-lg text-gray-900 dark:text-white font-bold tracking-wide">{scan.target}</p>
                                <p className="text-sm text-gray-500 dark:text-gray-400 font-mono mt-1">
                                    {(() => {
                                        const nslookup = scan.results?.find((r: any) => r.tool === 'NSLookup');
                                        if (nslookup?.output_json) {
                                            try {
                                                const data = JSON.parse(nslookup.output_json);
                                                return data.ip || 'Scanning...';
                                            } catch (e) {}
                                        }
                                        const ipMatch = nslookup?.raw_output?.match(/Address:\s*(\d+\.\d+\.\d+\.\d+)/);
                                        return ipMatch ? ipMatch[1] : 'Scanning...';
                                    })()}
                                </p>
                            </div>
                        </div>

                        {/* Hosting & Location Grid */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="flex items-center gap-3">
                                <Server className="w-4 h-4 text-gray-500" />
                                <div>
                                    <p className="text-xs text-gray-500 uppercase font-medium">Hosting</p>
                                    <p className="text-sm text-gray-900 dark:text-white font-medium">
                                        {(() => {
                                            const whois = scan.results?.find((r: any) => r.tool === 'Whois');
                                            const orgMatch = whois?.raw_output?.match(/Registrar:\s*(.*)/i) || whois?.raw_output?.match(/OrgName:\s*(.*)/i);
                                            return orgMatch ? orgMatch[1].trim().substring(0, 15) + (orgMatch[1].length > 15 ? '...' : '') : 'Unknown';
                                        })()}
                                    </p>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <MapPin className="w-4 h-4 text-gray-500" />
                                <div>
                                    <p className="text-xs text-gray-500 uppercase font-medium">Location</p>
                                    <p className="text-sm text-gray-900 dark:text-white font-medium">
                                        {(() => {
                                            const whois = scan.results?.find((r: any) => r.tool === 'Whois');
                                            const countryMatch = whois?.raw_output?.match(/Country:\s*(.*)/i);
                                            const cityMatch = whois?.raw_output?.match(/City:\s*(.*)/i);
                                            if (cityMatch && countryMatch) return `${cityMatch[1].trim()}, ${countryMatch[1].trim()}`;
                                            return countryMatch ? countryMatch[1].trim() : 'Unknown';
                                        })()}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* SSL/TLS Status */}
                        <div className="bg-green-50 dark:bg-green-500/10 border border-green-200 dark:border-green-500/20 rounded-xl p-4">
                            <div className="flex items-center gap-2 mb-2">
                                <Shield className="w-4 h-4 text-green-600 dark:text-green-500" />
                                <span className="text-green-700 dark:text-green-500 font-bold text-sm">SSL/TLS Enabled</span>
                            </div>
                            <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                                <span>Version: <span className="text-gray-700 dark:text-gray-300">
                                    {(() => {
                                        const sslscan = scan.results?.find((r: any) => r.tool === 'SSLScan');
                                        if (sslscan?.raw_output) {
                                            // Look for accepted TLS versions (case insensitive, handle potential extra spaces)
                                            const tlsVersions = sslscan.raw_output.match(/Accepted\s+(TLSv\d\.\d|SSLv\d)/gi);
                                            if (tlsVersions && tlsVersions.length > 0) {
                                                // Get the highest version
                                                // Extract just the version part (e.g., "TLSv1.3")
                                                const versions = tlsVersions.map((v: string) => {
                                                    const match = v.match(/(TLSv\d\.\d|SSLv\d)/i);
                                                    return match ? match[1] : '';
                                                }).filter(Boolean).sort();
                                                return versions[versions.length - 1];
                                            }
                                        }
                                        // Fallback to WhatWeb
                                        const whatweb = scan.results?.find((r: any) => r.tool === 'WhatWeb');
                                        if (whatweb?.raw_output) {
                                            if (whatweb.raw_output.includes('https://')) return 'TLS Enabled';
                                        }
                                        return 'Unknown';
                                    })()}
                                </span></span>
                                <span>Issuer: <span className="text-gray-700 dark:text-gray-300">
                                    {(() => {
                                        const sslscan = scan.results?.find((r: any) => r.tool === 'SSLScan');
                                        if (sslscan?.raw_output) {
                                            const issuerMatch = sslscan.raw_output.match(/Issuer:\s*(.*)/i);
                                            if (issuerMatch) {
                                                const issuer = issuerMatch[1].trim();
                                                // Map common intermediate certs to friendly names
                                                if (issuer.match(/Let's Encrypt|R3|E[5-9]|E1/i)) return "Let's Encrypt";
                                                if (issuer.match(/DigiCert/i)) return "DigiCert";
                                                if (issuer.match(/Cloudflare/i)) return "Cloudflare";
                                                if (issuer.match(/Google Trust Services/i)) return "Google";
                                                if (issuer.match(/Sectigo/i)) return "Sectigo";
                                                return issuer.substring(0, 20) + (issuer.length > 20 ? '...' : '');
                                            }
                                        }
                                        return 'Unknown';
                                    })()}
                                </span></span>
                            </div>
                        </div>

                        {/* Footer Stats Grid */}
                        <div className="grid grid-cols-3 gap-3 pt-2">
                            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center border border-gray-200 dark:border-gray-800">
                                <Database className="w-5 h-5 text-blue-500 mx-auto mb-2" />
                                <p className="text-xl font-bold text-gray-900 dark:text-white">
                                    {(() => {
                                        // Try Subfinder (Full) or Subfinder (Passive) or legacy Subfinder
                                        const subfinder = scan.results?.find((r: any) => 
                                            r.tool === 'Subfinder (Full)' || 
                                            r.tool === 'Subfinder (Passive)' || 
                                            r.tool === 'Subfinder'
                                        );
                                        
                                        if (subfinder?.output_json) {
                                            try {
                                                const data = JSON.parse(subfinder.output_json);
                                                // Assuming JSON array of domains or object with domains
                                                if (Array.isArray(data)) return data.length;
                                                if (data.domains && Array.isArray(data.domains)) return data.domains.length;
                                            } catch (e) {}
                                        }
                                        if (subfinder?.raw_output) {
                                            // Count lines that look like domains
                                            const lines = subfinder.raw_output.split('\n').filter((l: string) => l.trim() && l.includes('.'));
                                            return lines.length;
                                        }

                                        // Fallback to Sublist3r
                                        const sublist3r = scan.results?.find((r: any) => r.tool === 'Sublist3r');
                                        if (!sublist3r?.raw_output) return 0;
                                        const lines = sublist3r.raw_output.split('\n').filter((l: string) => l.includes(scan.target));
                                        return Math.max(0, lines.length - 2); 
                                    })()}
                                </p>
                                <p className="text-[10px] text-gray-500 uppercase">Subdomains</p>
                            </div>
                            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center border border-gray-200 dark:border-gray-800">
                                <Clock className="w-5 h-5 text-purple-500 mx-auto mb-2" />
                                <p className="text-xl font-bold text-gray-900 dark:text-white">
                                    {(() => {
                                        // 1. Check Ping (Fastest/Earliest)
                                        const ping = scan.results?.find((r: any) => r.tool === 'Ping');
                                        if (ping?.raw_output) {
                                            const timeMatch = ping.raw_output.match(/time=([\d\.]+)\s*ms/i);
                                            if (timeMatch) return `${Math.round(parseFloat(timeMatch[1]))}ms`;
                                        }

                                        // 2. Check Nmap Fast Scan
                                        const nmapFast = scan.results?.find((r: any) => r.tool === 'Nmap Fast Scan');
                                        if (nmapFast?.raw_output) {
                                             const latencyMatch = nmapFast.raw_output.match(/\(([\d\.]+)s latency\)/);
                                             if (latencyMatch) return `${Math.round(parseFloat(latencyMatch[1]) * 1000)}ms`;
                                        }

                                        // 3. Check Nmap Top 1000 (Existing)
                                        const nmap = scan.results?.find((r: any) => r.tool === 'Nmap Top 1000');
                                        if (nmap?.raw_output) {
                                            // Look for "Host is up (0.00012s latency)"
                                            const latencyMatch = nmap.raw_output.match(/latency\)\.\s*rtt-range:\s*([\d\.]+)-([\d\.]+)/i) || 
                                                                 nmap.raw_output.match(/\(([\d\.]+)s latency\)/);
                                            
                                            if (latencyMatch) {
                                                const seconds = parseFloat(latencyMatch[1]);
                                                if (!isNaN(seconds)) {
                                                    const ms = Math.round(seconds * 1000);
                                                    return `${ms}ms`;
                                                }
                                            }
                                        }
                                        return 'N/A';
                                    })()}
                                </p>
                                <p className="text-[10px] text-gray-500 uppercase">Response</p>
                            </div>
                            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center border border-gray-200 dark:border-gray-800">
                                <Server className="w-5 h-5 text-orange-500 mx-auto mb-2" />
                                <p className="text-xl font-bold text-gray-900 dark:text-white">
                                    {(() => {
                                        const nslookup = scan.results?.find((r: any) => r.tool === 'NSLookup');
                                        if (!nslookup?.raw_output) return 0;
                                        // Count lines with "Address" or "Name"
                                        const matches = nslookup.raw_output.match(/(Address|Name):/g);
                                        return matches ? Math.floor(matches.length / 2) + 2 : 0;
                                    })()}
                                </p>
                                <p className="text-[10px] text-gray-500 uppercase">DNS Records</p>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Scan Progress Card */}
                <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-6 flex flex-col gap-6 shadow-sm">
                    {/* Header & Main Progress */}
                    <div>
                        <div className="flex justify-between items-end mb-2">
                            <div>
                                <h3 className="text-gray-900 dark:text-white text-lg font-bold mb-6">Total Progress</h3>
                                <div className="flex items-center gap-2 mt-1">
                                    <span className="text-sm text-gray-500">Current Phase:</span>
                                    <span className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
                                        {progressMetrics.currentPhase === 'Completed' ? (
                                            <CheckCircle className="w-4 h-4 text-green-500" />
                                        ) : (
                                            <Activity className="w-4 h-4 text-blue-500 animate-pulse" />
                                        )}
                                        {progressMetrics.currentPhase}
                                    </span>
                                </div>
                            </div>
                            <span className="text-3xl font-bold text-blue-600 dark:text-blue-500">{progressMetrics.percent}%</span>
                        </div>
                        <div className="w-full h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                            <div 
                                className="h-full bg-gradient-to-r from-blue-600 to-purple-600 rounded-full transition-all duration-500 ease-out"
                                style={{ width: `${progressMetrics.percent}%` }}
                            ></div>
                        </div>
                        <div className="flex justify-between mt-2 text-xs text-gray-500">
                            <span>{progressMetrics.completed} / {progressMetrics.total} steps completed</span>
                            <span>{scan.status}</span>
                        </div>
                    </div>

                    {/* Current Activity */}
                    {progressMetrics.currentTool && scan.status === 'Running' && (
                        <div className="bg-blue-50 dark:bg-blue-500/5 border border-blue-200 dark:border-blue-500/10 rounded-lg p-4 flex items-center gap-4">
                            <div className="p-2 bg-blue-100 dark:bg-blue-500/10 rounded-lg">
                                <Terminal className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                            </div>
                            <div className="flex-1">
                                <p className="text-xs text-blue-600 dark:text-blue-400 font-medium uppercase mb-0.5">Currently Executing</p>
                                <p className="text-sm text-gray-700 dark:text-gray-200 font-mono">
                                    {progressMetrics.currentTool.tool === 'AI_PHASE_SUMMARY' ? 'AI Analysis' : progressMetrics.currentTool.tool}
                                </p>
                            </div>
                            <div className="text-xs text-gray-500 font-mono">
                                <Clock className="w-3 h-3 inline mr-1" />
                                {elapsedTime}s
                            </div>
                        </div>
                    )}

                    {/* Phase Summary */}
                    <div className="space-y-3 pt-2 border-t border-gray-200 dark:border-gray-800">
                        {phases.map((phase: string) => {
                            const p = progressMetrics.phaseProgress[phase];
                            if (!p) return null;
                            const phasePercent = p.total > 0 ? (p.completed / p.total) * 100 : 0;
                            const isDone = p.completed === p.total;
                            const isActive = !isDone && p.running > 0;
                            
                            return (
                                <div key={phase} className="space-y-1">
                                    <div className="flex justify-between text-xs">
                                        <span className={`font-medium ${isActive ? 'text-blue-600 dark:text-blue-400' : isDone ? 'text-green-600 dark:text-green-500' : 'text-gray-500'}`}>
                                            {phase}
                                        </span>
                                        <span className="text-gray-500 dark:text-gray-600">{p.completed}/{p.total}</span>
                                    </div>
                                    <div className="w-full h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                                        <div 
                                            className={`h-full rounded-full transition-all duration-500 ${isDone ? 'bg-green-500' : isActive ? 'bg-blue-500' : 'bg-gray-300 dark:bg-gray-700'}`}
                                            style={{ width: `${phasePercent}%` }}
                                        ></div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>

            {/* Tabs */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
                <div className="flex border-b border-gray-200 dark:border-gray-800 overflow-x-auto">
                    <button 
                        className={`py-3 px-6 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${activeTab === 'summary' ? 'text-blue-600 dark:text-white border-b-2 border-blue-600 dark:border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                        onClick={() => handleTabChange('summary')}
                    >
                        <Bot className="w-4 h-4" />
                        AI Summary
                    </button>
                    <button 
                        className={`py-3 px-6 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${activeTab === 'findings' ? 'text-blue-600 dark:text-white border-b-2 border-blue-600 dark:border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                        onClick={() => handleTabChange('findings')}
                    >
                        <Shield className="w-4 h-4" />
                        Findings ({allFindings.length})
                    </button>
                    {(scan.results?.some((r: any) => r.tool === 'WebScraperRecon' || r.tool === 'WebScraperRecon (Active)')) && (
                        <button 
                            className={`py-3 px-6 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${activeTab === 'web-intel' ? 'text-blue-600 dark:text-white border-b-2 border-blue-600 dark:border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                            onClick={() => handleTabChange('web-intel')}
                        >
                            <Globe className="w-4 h-4" />
                            Web Intelligence
                        </button>
                    )}
                    <button 
                        className={`py-3 px-6 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${activeTab === 'logs' ? 'text-blue-600 dark:text-white border-b-2 border-blue-600 dark:border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                        onClick={() => handleTabChange('logs')}
                    >
                        <Terminal className="w-4 h-4" />
                        Raw Logs
                    </button>
                    <button 
                        className={`py-3 px-6 text-sm font-medium flex items-center gap-2 whitespace-nowrap transition-colors ${activeTab === 'report' ? 'text-blue-600 dark:text-white border-b-2 border-blue-600 dark:border-blue-500' : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'}`}
                        onClick={() => handleTabChange('report')}
                    >
                        <FileText className="w-4 h-4" />
                        Report
                    </button>
                </div>

                <div className="p-6 relative min-h-[400px]">
                    <AnimatePresence mode="wait" custom={direction}>
                        {activeTab === 'findings' && (
                            <motion.div
                                key="findings"
                                variants={slideVariants}
                                custom={direction}
                                initial="enter"
                                animate="center"
                                exit="exit"
                                transition={{ duration: 0.3, ease: "easeInOut" }}
                            >
                            {/* Filters */}
                            {/* Filters */}
                            <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
                                {['All', 'Critical', 'High', 'Medium', 'Low'].map((severity) => {
                                    const count = severity === 'All' 
                                        ? allFindings.length 
                                        : severityCounts[severity as keyof typeof severityCounts];
                                    
                                    return (
                                        <button
                                            key={severity}
                                            onClick={() => setSeverityFilter(severity)}
                                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors border ${
                                                severityFilter === severity
                                                    ? 'bg-blue-600 text-white border-blue-600'
                                                    : 'bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 hover:text-gray-900 dark:hover:text-gray-300'
                                            }`}
                                        >
                                            {severity} <span className="ml-1 opacity-60">({count})</span>
                                        </button>
                                    );
                                })}
                            </div>

                            {/* Findings List */}
                            {filteredFindings.length === 0 ? (
                                <div className="text-gray-500 text-center py-12 bg-gray-50 dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 border-dashed">
                                    <Shield className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                    <p>No findings match the selected filter.</p>
                                </div>
                            ) : (
                                <motion.div 
                                    variants={containerVariants}
                                    initial="hidden"
                                    animate="show"
                                    className="space-y-4"
                                >
                                    {filteredFindings.map((finding: any, index: number) => {
                                        const isExpanded = expandedFinding === index;
                                        
                                        return (
                                            <motion.div variants={itemVariants} key={index} className={`bg-white dark:bg-gray-900 rounded-xl border transition-all duration-200 ${isExpanded ? 'border-blue-500/30 ring-1 ring-blue-500/30 shadow-md' : 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700 shadow-sm'}`}>
                                                {/* Card Header */}
                                                <div 
                                                    className="p-5 cursor-pointer flex items-start gap-4"
                                                    onClick={() => setExpandedFinding(isExpanded ? null : index)}
                                                >
                                                    <div className={`mt-1 p-2 rounded-lg ${
                                                        finding.Severity === 'Critical' ? 'bg-red-100 dark:bg-red-500/10 text-red-600 dark:text-red-500' :
                                                        finding.Severity === 'High' ? 'bg-orange-100 dark:bg-orange-500/10 text-orange-600 dark:text-orange-500' :
                                                        finding.Severity === 'Medium' ? 'bg-yellow-100 dark:bg-yellow-500/10 text-yellow-600 dark:text-yellow-500' :
                                                        'bg-blue-100 dark:bg-blue-500/10 text-blue-600 dark:text-blue-500'
                                                    }`}>
                                                        <AlertTriangle className="w-5 h-5" />
                                                    </div>
                                                    
                                                    <div className="flex-1">
                                                        <div className="flex items-center justify-between mb-1">
                                                            <h4 className="text-lg font-medium text-gray-900 dark:text-white">
                                                                {finding.Heading || finding.Vulnerability}
                                                            </h4>
                                                            <div className="flex items-center gap-3">
                                                                {/* OWASP & CWE Badges */}
                                                                {(finding.OWASP || finding.CWE) && (
                                                                    <div className="flex gap-2 mr-2">
                                                                        {finding.OWASP && (
                                                                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-purple-100 dark:bg-purple-500/10 text-purple-700 dark:text-purple-400 border border-purple-200 dark:border-purple-500/20">
                                                                                {finding.OWASP}
                                                                            </span>
                                                                        )}
                                                                        {finding.CWE && (
                                                                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 border border-gray-200 dark:border-gray-600">
                                                                                {finding.CWE}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                )}

                                                                <span className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
                                                                    finding.Severity === 'Critical' ? 'bg-red-500 text-white' :
                                                                    finding.Severity === 'High' ? 'bg-orange-500 text-white' :
                                                                    finding.Severity === 'Medium' ? 'bg-yellow-500 text-black' :
                                                                    'bg-blue-500 text-white'
                                                                }`}>
                                                                    {finding.Severity}
                                                                </span>
                                                                <div className={`transform transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}>
                                                                    <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                                                                    </svg>
                                                                </div>
                                                            </div>
                                                        </div>
                                                        {/* Show Description only when expanded, or show a summary line when collapsed if Heading is used as title */}
                                                        {!isExpanded && (
                                                            <p className="text-gray-500 dark:text-gray-400 text-sm line-clamp-1">
                                                                {finding.Heading ? finding.Vulnerability : finding.Description}
                                                            </p>
                                                        )}
                                                        
                                                        {!isExpanded && (
                                                            <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
                                                                <span className="flex items-center gap-1.5">
                                                                    <Shield className="w-3.5 h-3.5" /> {finding.tool}
                                                                </span>
                                                                <span className="flex items-center gap-1.5">
                                                                    <Clock className="w-3.5 h-3.5" /> {new Date(finding.timestamp).toLocaleString()}
                                                                </span>
                                                            </div>
                                                        )}
                                                    </div>
                                                </div>

                                                {/* Expanded Content */}
                                                {isExpanded && (
                                                    <div className="px-5 pb-5 pl-[4.5rem]">
                                                        {/* Full Description if Heading is used, or just Description */}
                                                        <div className="mb-6">
                                                            <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Description</h5>
                                                            <p className="text-sm text-gray-600 dark:text-gray-300 leading-relaxed">
                                                                {finding.Description}
                                                            </p>
                                                        </div>

                                                        {/* Evidence Section */}
                                                        {finding.Evidence && (
                                                            <div className="mb-6">
                                                                <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Evidence / Proof of Concept</h5>
                                                                <div className="bg-gray-50 dark:bg-black/30 rounded-lg border border-gray-200 dark:border-gray-800 p-4 font-mono text-xs text-gray-600 dark:text-gray-300 overflow-x-auto">
                                                                    <pre>{finding.Evidence}</pre>
                                                                </div>
                                                            </div>
                                                        )}

                                                        {/* Metadata Row */}
                                                        <div className="flex items-center gap-6 mb-6 text-sm text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-800 pb-4">
                                                            <div className="flex items-center gap-2">
                                                                <Shield className="w-4 h-4" />
                                                                <span>Source: <span className="text-gray-700 dark:text-gray-300">{finding.tool}</span></span>
                                                            </div>
                                                            <div className="flex items-center gap-2">
                                                                <Clock className="w-4 h-4" />
                                                                <span>Detected: <span className="text-gray-700 dark:text-gray-300">{new Date(finding.timestamp).toLocaleString()}</span></span>
                                                            </div>
                                                        </div>

                                                        {/* Affected Assets */}
                                                        <div className="mb-6">
                                                            <h5 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Affected Assets</h5>
                                                            <div className="flex flex-wrap gap-2">
                                                                <span className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-md text-sm text-gray-700 dark:text-gray-300 font-mono border border-gray-200 dark:border-gray-700 flex items-center gap-2">
                                                                    {scan.target}
                                                                    <button 
                                                                        className="hover:text-gray-900 dark:hover:text-white transition-colors"
                                                                        onClick={() => {
                                                                            navigator.clipboard.writeText(scan.target);
                                                                            // Optional: Add toast or visual feedback here
                                                                        }}
                                                                        title="Copy to clipboard"
                                                                    >
                                                                        <Copy className="w-3 h-3" />
                                                                    </button>
                                                                </span>
                                                                {/* Mock additional assets if needed */}
                                                                {finding.Description?.includes('subdomain') && (
                                                                    <span className="px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-md text-sm text-gray-700 dark:text-gray-300 font-mono border border-gray-200 dark:border-gray-700 flex items-center gap-2">
                                                                        www.{scan.target}
                                                                        <button 
                                                                            className="hover:text-gray-900 dark:hover:text-white transition-colors"
                                                                            onClick={() => navigator.clipboard.writeText(`www.${scan.target}`)}
                                                                            title="Copy to clipboard"
                                                                        >
                                                                            <Copy className="w-3 h-3" />
                                                                        </button>
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </div>

                                                        {/* Remediation Box */}
                                                        <div className="bg-blue-50 dark:bg-blue-500/5 border border-blue-200 dark:border-blue-500/10 rounded-lg p-4 mb-6">
                                                            <div className="flex items-center gap-2 mb-2">
                                                                <Shield className="w-4 h-4 text-blue-600 dark:text-blue-400" />
                                                                <h5 className="text-sm font-medium text-blue-600 dark:text-blue-400">Remediation Recommendation</h5>
                                                            </div>
                                                            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">
                                                                {finding.Remediation || finding.Mitigation || "No specific remediation provided. Please review standard security practices for this vulnerability type."}
                                                            </p>
                                                        </div>

                                                        {/* Action Buttons */}
                                                        <div className="flex items-center gap-3">
                                                            <button 
                                                                onClick={() => setSelectedFinding(finding)}
                                                                className="px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 transition-colors flex items-center gap-2 shadow-sm"
                                                            >
                                                                <FileText className="w-4 h-4" /> View Details
                                                            </button>
                                                            <button 
                                                                onClick={() => handleCreateTicket(finding)}
                                                                className="px-4 py-2 bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-lg border border-gray-200 dark:border-gray-700 transition-colors flex items-center gap-2 shadow-sm"
                                                            >
                                                                <Copy className="w-4 h-4" /> Create Ticket
                                                            </button>
                                                        </div>
                                                    </div>
                                                )}
                                            </motion.div>
                                        );
                                    })}
                                </motion.div>
                            )}
                        </motion.div>
                    )}
                    </AnimatePresence>

            {/* View Details Modal */}
            <Modal
                isOpen={!!selectedFinding}
                onClose={() => setSelectedFinding(null)}
                title="Vulnerability Details"
            >
                {selectedFinding && (
                    <div className="space-y-4">
                        <div>
                            <h4 className="text-sm font-medium text-gray-400 mb-1">Description</h4>
                            <p className="text-gray-200">{selectedFinding.Description}</p>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div>
                                <h4 className="text-sm font-medium text-gray-400 mb-1">Severity</h4>
                                <span className={`inline-block px-2 py-1 rounded text-xs font-bold ${
                                    selectedFinding.Severity === 'CRITICAL' ? 'bg-red-500/20 text-red-500' :
                                    selectedFinding.Severity === 'HIGH' ? 'bg-orange-500/20 text-orange-500' :
                                    selectedFinding.Severity === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-500' :
                                    'bg-blue-500/20 text-blue-500'
                                }`}>
                                    {selectedFinding.Severity}
                                </span>
                            </div>
                            <div>
                                <h4 className="text-sm font-medium text-gray-400 mb-1">CWE ID</h4>
                                <span className="text-gray-200 font-mono">{selectedFinding.CWE || 'N/A'}</span>
                            </div>
                        </div>
                        <div>
                            <h4 className="text-sm font-medium text-gray-400 mb-1">Remediation</h4>
                            <p className="text-gray-200">{selectedFinding.Remediation || selectedFinding.Mitigation || 'N/A'}</p>
                        </div>
                        <div>
                            <h4 className="text-sm font-medium text-gray-400 mb-1">Raw Data</h4>
                            <pre className="bg-black/50 p-4 rounded-lg overflow-x-auto text-xs font-mono text-green-400">
                                {JSON.stringify(selectedFinding, null, 2)}
                            </pre>
                        </div>
                    </div>
                )}
            </Modal>

                    {activeTab === 'summary' && (
                        <motion.div 
                            key="summary"
                            variants={slideVariants}
                            custom={direction}
                            initial="enter"
                            animate="center"
                            exit="exit"
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                            className="space-y-8"
                        >
                            {(() => {
                                // Group results by phase
                                const groupedResults: { [key: string]: any[] } = {};
                                scan.results?.forEach((result: any) => {
                                    // Only show Phase Summaries
                                    if (result.tool === 'AI_PHASE_SUMMARY' && result.gemini_summary) {
                                        const phase = result.phase || 'Other';
                                        if (!groupedResults[phase]) {
                                            groupedResults[phase] = [];
                                        }
                                        groupedResults[phase].push(result);
                                    }
                                });

                                const phaseOrder = [
                                    "Passive Recon", 
                                    "Asset Discovery", 
                                    "Active Recon", 
                                    "Enumeration", 
                                    "Vulnerability Analysis"
                                ];
                                
                                const sortedPhases = Object.keys(groupedResults).sort((a, b) => {
                                    const indexA = phaseOrder.indexOf(a);
                                    const indexB = phaseOrder.indexOf(b);
                                    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                                    if (indexA !== -1) return -1;
                                    if (indexB !== -1) return 1;
                                    return a.localeCompare(b);
                                });

                                if (sortedPhases.length === 0) {
                                    return (
                                        <div className="text-gray-500 text-center py-12 bg-gray-900/50 rounded-xl border border-gray-800 border-dashed">
                                            <Activity className="w-12 h-12 mx-auto mb-4 opacity-20" />
                                            <p>No AI summaries available yet.</p>
                                        </div>
                                    );
                                }

                                return sortedPhases.map((phase) => (
                                    <div key={phase} className="bg-white dark:bg-gray-950 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                                        <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900/50 border-b border-gray-200 dark:border-gray-800 flex items-center gap-3">
                                            <Activity className="w-5 h-5 text-blue-600 dark:text-blue-500" />
                                            <h3 className="text-lg font-medium text-gray-900 dark:text-white">{phase} Analysis</h3>
                                        </div>
                                        <div className="divide-y divide-gray-200 dark:divide-gray-800">
                                            {groupedResults[phase].map((result: any) => {
                                                let summary = "No summary available.";
                                                try {
                                                    const parsed = JSON.parse(result.gemini_summary);
                                                    summary = parsed.summary || result.gemini_summary;
                                                } catch (e) {
                                                    summary = result.gemini_summary;
                                                }

                                                return (
                                                    <div key={result.id} className="p-6">
                                                        {result.tool !== 'AI_PHASE_SUMMARY' && (
                                                            <div className="flex items-center gap-2 mb-3">
                                                                <Terminal className="w-4 h-4 text-gray-500" />
                                                                <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">{result.tool}</h4>
                                                            </div>
                                                        )}
                                                        <div className="prose prose-invert max-w-none text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                                                            {summary}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                ));
                            })()}
                        </motion.div>
                    )}

                    {activeTab === 'report' && (
                        <motion.div 
                            key="report"
                            variants={slideVariants}
                            custom={direction}
                            initial="enter"
                            animate="center"
                            exit="exit"
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                            className="flex flex-col items-center justify-center py-12 text-gray-500"
                        >
                            <FileText className="w-16 h-16 mb-4 opacity-20" />
                            <p className="mb-4">PDF Report Preview is available by downloading the file.</p>
                            {scan.pdfPath && (
                                <button 
                                    onClick={() => window.open(`http://localhost:8000/reports/${scan.pdfPath.split('\\').pop()}`, '_blank')}
                                    className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
                                >
                                    Download PDF Report
                                </button>
                            )}
                        </motion.div>
                    )}

                    {activeTab === 'logs' && (
                        <motion.div 
                            key="logs"
                            variants={slideVariants}
                            custom={direction}
                            initial="enter"
                            animate="center"
                            exit="exit"
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                            className="space-y-6"
                        >
                            {(() => {
                                // Group results by phase
                                const groupedResults: { [key: string]: any[] } = {};
                                scan.results?.forEach((result: any) => {
                                    // Skip AI Summary items for logs
                                    if (result.tool === 'AI_PHASE_SUMMARY') return;

                                    const phase = result.parent_phase_id || result.phase || 'Unknown Phase';
                                    if (!groupedResults[phase]) {
                                        groupedResults[phase] = [];
                                    }
                                    groupedResults[phase].push(result);
                                });

                                // Sort phases based on predefined order or appearance
                                const phaseOrder = [
                                    "Passive Recon", 
                                    "Asset Discovery", 
                                    "Active Recon", 
                                    "Enumeration", 
                                    "Vulnerability Analysis"
                                ];
                                
                                const sortedPhases = Object.keys(groupedResults).sort((a, b) => {
                                    const indexA = phaseOrder.indexOf(a);
                                    const indexB = phaseOrder.indexOf(b);
                                    if (indexA !== -1 && indexB !== -1) return indexA - indexB;
                                    if (indexA !== -1) return -1;
                                    if (indexB !== -1) return 1;
                                    return a.localeCompare(b);
                                });

                                return sortedPhases.map((phase) => {
                                    const tools = groupedResults[phase].sort((a, b) => (a.order_index || 0) - (b.order_index || 0));
                                    const completedCount = tools.filter(t => t.status === 'Completed').length;
                                    const failedCount = tools.filter(t => t.status === 'Failed').length;
                                    const runningCount = tools.filter(t => t.status === 'Running').length;
                                    const totalCount = tools.length;
                                    
                                    const isPhaseRunning = runningCount > 0;
                                    const isPhaseFailed = failedCount > 0 && runningCount === 0 && completedCount < totalCount;
                                    const isPhaseCompleted = completedCount === totalCount;

                                    return (
                                        <div key={phase} className="border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden bg-white dark:bg-gray-900/50 shadow-sm">
                                            {/* Phase Header */}
                                            <div className="px-6 py-4 bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
                                                <div className="flex items-center gap-3">
                                                    {isPhaseCompleted ? <CheckCircle className="w-5 h-5 text-green-500" /> :
                                                     isPhaseRunning ? <Activity className="w-5 h-5 text-blue-500 animate-pulse" /> :
                                                     isPhaseFailed ? <AlertTriangle className="w-5 h-5 text-red-500" /> :
                                                     <div className="w-5 h-5 rounded-full border-2 border-gray-300 dark:border-gray-700" />}
                                                    
                                                    <div>
                                                        <h3 className="text-lg font-medium text-gray-900 dark:text-white">{phase}</h3>
                                                        <p className="text-xs text-gray-500">
                                                            {completedCount}/{totalCount} tools completed
                                                            {failedCount > 0 && <span className="text-red-500 dark:text-red-400 ml-2">({failedCount} failed)</span>}
                                                        </p>
                                                    </div>
                                                </div>
                                                <div className="flex items-center gap-2">
                                                    {/* Progress Bar for Phase */}
                                                    <div className="w-24 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
                                                        <div 
                                                            className={`h-full rounded-full ${isPhaseFailed ? 'bg-red-500' : 'bg-blue-500'}`}
                                                            style={{ width: `${(completedCount / totalCount) * 100}%` }}
                                                        ></div>
                                                    </div>
                                                </div>
                                            </div>

                                            {/* Tools List */}
                                            <div className="divide-y divide-gray-200 dark:divide-gray-800/50">
                                                {tools.map((result: any, i: number) => {
                                                    let parsedOutput = null;
                                                    try {
                                                        parsedOutput = result.output_json ? JSON.parse(result.output_json) : JSON.parse(result.raw_output);
                                                    } catch (e) {
                                                        parsedOutput = result.raw_output;
                                                    }

                                                    const isCompleted = result.status === 'Completed';
                                                    const isFailed = result.status === 'Failed';
                                                    const isRunning = result.status === 'Running';

                                                    return (
                                                        <div key={i} className="bg-white dark:bg-gray-950/30">
                                                            <div className="px-6 py-3 flex justify-between items-center hover:bg-gray-50 dark:hover:bg-gray-900/50 transition-colors group">
                                                                <div className="flex items-center gap-3">
                                                                    <div className={`w-2 h-2 rounded-full ${
                                                                        isCompleted ? 'bg-green-500' :
                                                                        isFailed ? 'bg-red-500' :
                                                                        isRunning ? 'bg-blue-500 animate-pulse' : 'bg-gray-300 dark:bg-gray-700'
                                                                    }`} />
                                                                    <div className="flex flex-col">
                                                                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 group-hover:text-gray-900 dark:group-hover:text-white transition-colors">
                                                                            {result.tool}
                                                                        </span>
                                                                        {result.command && (
                                                                            <span className="font-mono text-[10px] text-gray-500 dark:text-gray-600 truncate max-w-md hidden group-hover:block transition-all">
                                                                                $ {result.command}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                                <div className="flex items-center gap-4">
                                                                    {result.exit_code !== undefined && result.exit_code !== null && result.exit_code !== 0 && (
                                                                        <span className="text-xs text-red-500 dark:text-red-400 font-mono bg-red-100 dark:bg-red-500/10 px-2 py-0.5 rounded">Exit: {result.exit_code}</span>
                                                                    )}
                                                                    <span className="text-xs text-gray-500 dark:text-gray-600 font-mono">
                                                                        {result.finished_at ? 
                                                                            `${((new Date(result.finished_at).getTime() - new Date(result.started_at || result.createdAt).getTime()) / 1000).toFixed(1)}s` 
                                                                            : isRunning ? 'Running...' : ''}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                            
                                                            {/* Output Area (Always visible if content exists, or could be collapsible) */}
                                                            <div className="px-6 pb-4 pl-11">
                                                                <div className="bg-gray-50 dark:bg-gray-950 rounded border border-gray-200 dark:border-gray-800/50 overflow-hidden">
                                                                    <div className="max-h-64 overflow-y-auto custom-scrollbar p-3">
                                                                        {parsedOutput && typeof parsedOutput === 'object' && Object.keys(parsedOutput).length > 0 ? (
                                                                            Object.entries(parsedOutput).map(([key, value]) => (
                                                                                <div key={key} className="mb-2 last:mb-0">
                                                                                    <div className="text-[10px] font-bold text-blue-600 dark:text-blue-500/80 uppercase mb-0.5">{key}</div>
                                                                                    <pre className="font-mono text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                                                                        {Array.isArray(value) ? (value.length ? value.map(v => typeof v === 'object' ? JSON.stringify(v) : v).join('\n') : 'No results') : String(value)}
                                                                                    </pre>
                                                                                </div>
                                                                            ))
                                                                        ) : (
                                                                            <pre className="font-mono text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                                                                                {String(parsedOutput || (result.raw_output ? result.raw_output : "No output generated."))}
                                                                            </pre>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    );
                                });
                            })()}
                            <div />
                        </motion.div>
                    )}
                    {activeTab === 'web-intel' && (
                        <motion.div 
                            key="web-intel"
                            variants={slideVariants}
                            custom={direction}
                            initial="enter"
                            animate="center"
                            exit="exit"
                            transition={{ duration: 0.3, ease: "easeInOut" }}
                        >
                            <WebIntelligence data={(() => {
                                // Prioritize Active scan results as they are more complete
                                const activeResult = scan.results?.find((r: any) => r.tool === 'Alive Web Hosts');
                                const passiveResult = scan.results?.find((r: any) => r.tool === 'WebScraperRecon');
                                
                                const result = activeResult || passiveResult;
                                
                                if (!result) return null;
                                try {
                                    return result.output_json ? JSON.parse(result.output_json) : null;
                                } catch (e) {
                                    return null;
                                }
                            })()} />
                        </motion.div>
                    )}
                </div>
            </div>
        </PageTransition>
    );
};

export default ScanDetails;
