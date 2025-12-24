
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import { Search, Filter, Trash2, Eye, AlertTriangle, CheckCircle, Clock, Activity, ChevronLeft, ChevronRight } from 'lucide-react';
import api from '../api/axios';
import { useSSE } from '../context/SSEContext';

const History = () => {
    const navigate = useNavigate();
    const { addEventListener, removeEventListener } = useSSE();
    const [scans, setScans] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [totalItems, setTotalItems] = useState(0);
    const limit = 10;

    const fetchScans = async (currentPage = 1, search = '') => {
        try {
            setLoading(true);
            const response = await api.get('/scans/', {
                params: {
                    page: currentPage,
                    limit: limit,
                    search: search
                }
            });
            
            const scanData = response.data.items;
            
            // Enrich scans with findings count
            const enrichedScans = scanData.map((s: any) => {
                const counts = { Critical: 0, High: 0, Medium: 0, Low: 0 };
                if (s.results) {
                    s.results.forEach((r: any) => {
                        if (r.gemini_summary) {
                            try {
                                const parsed = JSON.parse(r.gemini_summary);
                                if (parsed.vulnerabilities) {
                                    parsed.vulnerabilities.forEach((v: any) => {
                                        const sev = v.Severity;
                                        if (counts[sev as keyof typeof counts] !== undefined) {
                                            counts[sev as keyof typeof counts]++;
                                        }
                                    });
                                }
                            } catch (e) {}
                        }
                    });
                }
                return { ...s, findings: counts };
            });
            
            setScans(enrichedScans);
            setTotalPages(response.data.pages);
            setTotalItems(response.data.total);
            setPage(response.data.page);
        } catch (error) {
            console.error('Failed to fetch scans:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        // Debounce search
        const timeoutId = setTimeout(() => {
            setPage(1); // Reset to page 1 on search
            fetchScans(1, searchTerm);
        }, 500);

        return () => clearTimeout(timeoutId);
    }, [searchTerm]);

    useEffect(() => {
        fetchScans(page, searchTerm);
    }, [page]); // Re-fetch on page change

    useEffect(() => {
        const onScanUpdate = (data: any) => {
            console.log("History received update:", data);
            fetchScans(page, searchTerm);
        };

        addEventListener("SCAN_UPDATE", onScanUpdate);

        return () => {
            removeEventListener("SCAN_UPDATE", onScanUpdate);
        };
    }, [page, searchTerm]);

    const handleDelete = async (e: React.MouseEvent, scanId: number) => {
        e.stopPropagation(); // Prevent row click
        if (window.confirm('Are you sure you want to delete this scan? This action cannot be undone.')) {
            try {
                await api.delete(`/scans/${scanId}`);
                fetchScans(page, searchTerm); // Refresh current list
            } catch (error) {
                console.error('Failed to delete scan:', error);
                alert('Failed to delete scan');
            }
        }
    };

    return (
        <PageTransition>
            <div className="flex justify-between items-center mb-8">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Scan History</h1>
                    <p className="text-sm text-gray-500 mt-1">View and manage your past security scans</p>
                </div>
                <div className="flex gap-4">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                        <input
                            type="text"
                            placeholder="Search scans..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 text-gray-900 dark:text-white pl-10 pr-4 py-2 rounded-lg focus:outline-none focus:border-blue-500 w-64 shadow-sm"
                        />
                    </div>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="bg-gray-50 dark:bg-gray-900/50 text-xs uppercase text-gray-500 border-b border-gray-200 dark:border-gray-800">
                                <th className="px-6 py-4 font-medium">Scan ID</th>
                                <th className="px-6 py-4 font-medium">Target</th>
                                <th className="px-6 py-4 font-medium">Status</th>
                                <th className="px-6 py-4 font-medium">Findings</th>
                                <th className="px-6 py-4 font-medium">Duration</th>
                                <th className="px-6 py-4 font-medium">Time</th>
                                <th className="px-6 py-4 font-medium text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-200 dark:divide-gray-800">
                            {loading ? (
                                <tr>
                                    <td colSpan={7} className="px-6 py-12 text-center">
                                        <div className="flex items-center justify-center">
                                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                                        </div>
                                    </td>
                                </tr>
                            ) : (
                                <AnimatePresence mode="popLayout">
                                {scans.map((scan: any) => (
                                    <motion.tr 
                                        layout
                                        initial={{ opacity: 0, y: 20 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95 }}
                                        transition={{ duration: 0.2 }}
                                        key={scan.id} 
                                        onClick={() => navigate(`/scan/${scan.id}`)}
                                        className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors cursor-pointer group"
                                    >
                                        <td className="px-6 py-4 text-sm font-mono text-blue-600 dark:text-blue-500">#{scan.scan_number}</td>
                                        <td className="px-6 py-4 text-sm text-gray-900 dark:text-white font-medium">{scan.target}</td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                                                scan.status === 'Completed' ? 'bg-green-100 dark:bg-green-500/10 text-green-700 dark:text-green-500 border-green-200 dark:border-green-500/20' :
                                                scan.status === 'Failed' ? 'bg-red-100 dark:bg-red-500/10 text-red-700 dark:text-red-500 border-red-200 dark:border-red-500/20' :
                                                'bg-blue-100 dark:bg-blue-500/10 text-blue-700 dark:text-blue-500 border-blue-200 dark:border-blue-500/20'
                                            }`}>
                                                {scan.status === 'Completed' && <CheckCircle className="w-3 h-3 mr-1" />}
                                                {scan.status === 'Failed' && <AlertTriangle className="w-3 h-3 mr-1" />}
                                                {scan.status === 'Running' && <Activity className="w-3 h-3 mr-1 animate-pulse" />}
                                                {scan.status}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            {scan.findings && (
                                            <div className="flex items-center gap-3 text-xs font-mono">
                                                <span className="text-red-600 dark:text-red-500">C:{scan.findings.Critical}</span>
                                                <span className="text-orange-600 dark:text-orange-500">H:{scan.findings.High}</span>
                                                <span className="text-yellow-600 dark:text-yellow-500">M:{scan.findings.Medium}</span>
                                                <span className="text-blue-600 dark:text-blue-500">L:{scan.findings.Low}</span>
                                            </div>
                                            )}
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                                            <div className="flex items-center gap-1">
                                                <Clock className="w-3 h-3" />
                                                {(() => {
                                                    if (!scan.results || scan.results.length === 0) return '-';
                                                    const endTimes = scan.results
                                                        .map((r: any) => r.finished_at ? new Date(r.finished_at).getTime() : 0)
                                                        .filter((t: number) => t > 0);
                                                    const startTimes = scan.results
                                                        .map((r: any) => r.started_at ? new Date(r.started_at).getTime() : 0)
                                                        .filter((t: number) => t > 0);
                                                    
                                                    if (endTimes.length === 0) return '-';
                                                    
                                                    const end = Math.max(...endTimes);
                                                    const start = startTimes.length > 0 ? Math.min(...startTimes) : new Date(scan.date).getTime();
                                                    
                                                    const diff = Math.max(0, end - start);
                                                    const seconds = Math.round(diff / 1000);
                                                    
                                                    if (seconds === 0) return '< 1s';
                                                    if (seconds < 60) return `${seconds}s`;
                                                    return `${Math.round(seconds / 60)}m`;
                                                })()}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-sm text-gray-500 dark:text-gray-400">
                                            {new Date(scan.date).toLocaleDateString()}
                                        </td>
                                        <td className="px-6 py-4 text-right">
                                            <div className="flex items-center justify-end gap-2">
                                                <button 
                                                    onClick={(e) => { e.stopPropagation(); navigate(`/scan/${scan.id}`); }}
                                                    className="p-2 text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                                                    title="View Details"
                                                >
                                                    <Eye className="w-4 h-4" />
                                                </button>
                                                <button 
                                                    onClick={(e) => handleDelete(e, scan.id)}
                                                    className="p-2 text-gray-400 hover:text-red-600 dark:hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                                    title="Delete Scan"
                                                >
                                                    <Trash2 className="w-4 h-4" />
                                                </button>
                                            </div>
                                        </td>
                                    </motion.tr>
                                ))}
                                </AnimatePresence>
                            )}
                            
                            {!loading && scans.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="px-6 py-12 text-center text-gray-500">
                                        <div className="flex flex-col items-center justify-center">
                                            <Search className="w-8 h-8 mb-3 opacity-50" />
                                            <p>No scans found matching your criteria</p>
                                        </div>
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>

                    {/* Pagination Controls */}
                    {!loading && totalItems > 0 && (
                        <div className="flex items-center justify-between px-6 py-4 border-t border-gray-200 dark:border-gray-800">
                            <div className="text-sm text-gray-500 dark:text-gray-400">
                                Showing <span className="font-medium">{(page - 1) * limit + 1}</span> to <span className="font-medium">{Math.min(page * limit, totalItems)}</span> of <span className="font-medium">{totalItems}</span> results
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(1, p - 1))}
                                    disabled={page === 1}
                                    className="p-2 border border-gray-200 dark:border-gray-800 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed text-gray-500 dark:text-gray-400"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                                <span className="text-sm text-gray-700 dark:text-gray-300 px-2">
                                    Page {page} of {totalPages}
                                </span>
                                <button
                                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                                    disabled={page === totalPages}
                                    className="p-2 border border-gray-200 dark:border-gray-800 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed text-gray-500 dark:text-gray-400"
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </PageTransition>
    );
};

export default History;
