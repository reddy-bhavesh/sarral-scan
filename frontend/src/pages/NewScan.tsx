import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import { Target, Search, AlertTriangle, CheckCircle, Loader2, Play, ArrowLeft } from 'lucide-react';
import api from '../api/axios';

const NewScan = () => {
    const navigate = useNavigate();
    const [target, setTarget] = useState('');
    const [selectedPhases, setSelectedPhases] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [sshStatus, setSshStatus] = useState<'checking' | 'connected' | 'error'>('checking');
    const [sshMessage, setSshMessage] = useState('');

    const phases = {
        'Reconnaissance': [
            {
                id: 'Passive Recon',
                description: 'Gather information without directly interacting with the target',
                tools: ['Whois', 'NSLookup', 'Subfinder (Passive)', 'Amass Passive', 'Assetfinder', 'WebScraperRecon']
            },
            {
                id: 'Active Recon',
                description: 'Actively probe the target for information',
                tools: ['Nmap Top 1000', 'WhatWeb', 'WafW00f', 'SSLScan']
            }
        ],
        'Discovery': [
            {
                id: 'Asset Discovery',
                description: 'Discover all assets related to the target',
                tools: ['Subfinder (Full)', 'DNS Resolver', 'Alive Web Hosts']
            },
            {
                id: 'Enumeration',
                description: 'Enumerate services and directories',
                tools: ['FFUF', 'Nmap Vulnerability Scan']
            }
        ],
        'Vulnerability': [
            {
                id: 'Vulnerability Analysis',
                description: 'Scan for known vulnerabilities',
                tools: ['SQLMap', 'Dalfox', 'Nuclei']
            }
        ]
    };

    const checkSSH = async () => {
        setSshStatus('checking');
        setSshMessage('');
        try {
            const response = await api.get('/system/status');
            if (response.data.ssh_connection) {
                setSshStatus('connected');
                setSshMessage('Successfully connected to Kali VM');
            } else {
                setSshStatus('error');
                setSshMessage('Failed to connect to Kali VM. Please check your SSH configuration.');
            }
        } catch (error) {
            setSshStatus('error');
            setSshMessage('Failed to check system status. Backend might be down.');
        }
    };

    useEffect(() => {
        checkSSH();
    }, []);

    const togglePhase = (phase: string) => {
        if (selectedPhases.includes(phase)) {
            setSelectedPhases(selectedPhases.filter(p => p !== phase));
        } else {
            setSelectedPhases([...selectedPhases, phase]);
        }
    };

    const handleSubmit = async (e: React.FormEvent | React.MouseEvent) => {
        e.preventDefault();
        if (!target || selectedPhases.length === 0) return;

        setLoading(true);
        try {
            const response = await api.post('/scans/', {
                target,
                phases: selectedPhases
            });
            navigate(`/scan/${response.data.id}`);
        } catch (error) {
            console.error('Failed to start scan:', error);
            alert('Failed to start scan');
        } finally {
            setLoading(false);
        }
    };

    const totalPhases = Object.values(phases).reduce((acc, group) => acc + group.length, 0);

    return (
        <PageTransition className="relative">
            {/* Fixed Header */}
            <div className="fixed top-0 right-0 left-64 z-20 px-8 py-4 bg-white/95 dark:bg-gray-950/95 backdrop-blur supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-gray-950/60 border-b border-gray-200 dark:border-gray-800">
                <div className="max-w-6xl mx-auto flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button 
                            onClick={() => navigate(-1)}
                            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                        >
                            <ArrowLeft className="w-5 h-5" />
                        </button>
                        <div>
                            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Start New Scan</h1>
                            <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">Configure and launch a comprehensive security scan</p>
                        </div>
                    </div>
                    <button
                        onClick={handleSubmit}
                        disabled={loading || !target || selectedPhases.length === 0 || sshStatus === 'error'}
                        className={`px-6 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-all ${
                            loading || !target || selectedPhases.length === 0 || sshStatus === 'error'
                                ? 'bg-blue-600/50 text-white/50 cursor-not-allowed'
                                : 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-600/20'
                        }`}
                    >
                        {loading ? (
                            <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                            <Play className="w-4 h-4 fill-current" />
                        )}
                        Launch Scan
                    </button>
                </div>
            </div>

            {/* Spacer for Fixed Header */}
            <div className="h-24"></div>

            <div className="max-w-6xl mx-auto space-y-6">
                {/* Connection Status */}
                {sshStatus === 'checking' && (
                    <div className="bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/20 rounded-xl p-4 flex items-center gap-3 text-blue-600 dark:text-blue-400">
                        <Loader2 className="w-5 h-5 animate-spin" />
                        <span>Checking connection to Kali VM...</span>
                    </div>
                )}

                {sshStatus === 'connected' && (
                    <div className="bg-green-50 dark:bg-green-500/5 border border-green-200 dark:border-green-500/10 rounded-xl p-4 flex items-center gap-3">
                        <div className="p-1 rounded-full bg-green-100 dark:bg-green-500/10">
                            <CheckCircle className="w-5 h-5 text-green-600 dark:text-green-500" />
                        </div>
                        <div>
                            <p className="text-green-700 dark:text-green-500 font-medium text-sm">Connection Successful</p>
                            <p className="text-green-600/80 dark:text-green-500/60 text-xs">{sshMessage}</p>
                        </div>
                    </div>
                )}

                {sshStatus === 'error' && (
                    <div className="bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl p-4 flex items-center justify-between text-red-600 dark:text-red-400">
                        <div className="flex items-center gap-3">
                            <AlertTriangle className="w-5 h-5" />
                            <div>
                                <p className="font-medium">Connection Error</p>
                                <p className="text-sm opacity-90">{sshMessage}</p>
                            </div>
                        </div>
                        <button 
                            onClick={checkSSH}
                            className="px-4 py-2 bg-red-100 dark:bg-red-500/20 hover:bg-red-200 dark:hover:bg-red-500/30 rounded-lg text-sm font-medium transition-colors"
                        >
                            Retry
                        </button>
                    </div>
                )}

            {/* Target Configuration */}
            <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                    <Target className="w-5 h-5 text-blue-600 dark:text-blue-500" />
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Target Configuration</h2>
                </div>
                <div>
                    <label className="block text-xs font-medium text-gray-500 mb-2 uppercase">
                        Target URL or IP Address
                    </label>
                    <input
                        type="text"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                        placeholder="example.com or 192.168.1.1"
                        className="w-full bg-gray-50 dark:bg-gray-950 border border-gray-300 dark:border-gray-800 text-gray-900 dark:text-white px-4 py-3 rounded-lg focus:outline-none focus:border-blue-500 transition-colors placeholder-gray-400 dark:placeholder-gray-600"
                    />
                </div>
            </div>

            {/* Scan Phases */}
            <div className="bg-white dark:bg-gray-900/50 border border-gray-200 dark:border-gray-800 rounded-xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-6">
                    <div className="animate-spin-slow">
                        <Search className="w-5 h-5 text-blue-600 dark:text-blue-500" />
                    </div>
                    <h2 className="text-sm font-semibold text-gray-900 dark:text-white uppercase tracking-wider">Scan Phases</h2>
                </div>

                <div className="space-y-8">
                    {Object.entries(phases).map(([category, categoryPhases]) => (
                        <div key={category}>
                            <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-4 pl-1">
                                {category}
                            </h3>
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                {categoryPhases.map((phase, index) => {
                                    const isSelected = selectedPhases.includes(phase.id);
                                    return (
                                        <motion.div 
                                            initial={{ opacity: 0, y: 20 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: index * 0.1 }}
                                            key={phase.id}
                                            onClick={() => togglePhase(phase.id)}
                                            className={`cursor-pointer p-5 rounded-xl border transition-all duration-200 group ${
                                                isSelected
                                                    ? 'bg-blue-50 dark:bg-blue-500/5 border-blue-200 dark:border-blue-500/30'
                                                    : 'bg-gray-50 dark:bg-gray-950 border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'
                                            }`}
                                        >
                                            <div className="flex items-start justify-between mb-3">
                                                <div>
                                                    <h4 className={`font-medium mb-1 ${isSelected ? 'text-blue-900 dark:text-white' : 'text-gray-700 dark:text-gray-300'}`}>
                                                        {phase.id}
                                                    </h4>
                                                    <p className="text-xs text-gray-500 leading-relaxed">
                                                        {phase.description}
                                                    </p>
                                                </div>
                                                <div className={`w-5 h-5 rounded flex items-center justify-center border transition-colors ${
                                                    isSelected
                                                        ? 'bg-blue-600 border-blue-600'
                                                        : 'border-gray-300 dark:border-gray-700 group-hover:border-gray-400 dark:group-hover:border-gray-600'
                                                }`}>
                                                    {isSelected && <CheckCircle className="w-3.5 h-3.5 text-white" />}
                                                </div>
                                            </div>
                                            
                                            <div className="flex flex-wrap gap-2 mt-4">
                                                {phase.tools.map(tool => (
                                                    <span 
                                                        key={tool}
                                                        className={`px-2 py-1 rounded text-[10px] font-mono border ${
                                                            isSelected
                                                                ? 'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-200 dark:border-blue-500/20'
                                                                : 'bg-white dark:bg-gray-900 text-gray-500 border-gray-200 dark:border-gray-800'
                                                        }`}
                                                    >
                                                        {tool}
                                                    </span>
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

            {/* Summary Footer */}
            <div className="bg-blue-50 dark:bg-blue-500/5 border border-blue-100 dark:border-blue-500/10 rounded-xl p-6">
                <div className="flex items-center justify-between">
                    <div className="space-y-1">
                        <p className="text-sm text-blue-600 dark:text-blue-400">
                            Selected phases: <span className="font-bold text-gray-900 dark:text-white">{selectedPhases.length} of {totalPhases}</span>
                        </p>
                        <p className="text-xs text-gray-500">
                            Estimated scan duration: 15-25 minutes depending on target size
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </PageTransition>
    );
};

export default NewScan;
