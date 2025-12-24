import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import PageTransition from '../components/PageTransition';
import { 
    Activity, AlertTriangle, CheckCircle, Server, Play, 
    ArrowUpRight, ArrowDownRight, Eye, Clock 
} from 'lucide-react';
import api from '../api/axios';
import { useSSE } from '../context/SSEContext';

const containerVariants = {
    hidden: { opacity: 0 },
    show: {
        opacity: 1,
        transition: {
            staggerChildren: 0.1
        }
    }
};

const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0 }
};

const Dashboard = () => {
    const navigate = useNavigate();
    const { addEventListener, removeEventListener } = useSSE();
    const [loading, setLoading] = useState(true);
    const [stats, setStats] = useState<any[]>([]);
    const [recentScans, setRecentScans] = useState<any[]>([]);
    const [trendData, setTrendData] = useState<any[]>([]);
    const [vulnDist, setVulnDist] = useState<any>({ Critical: 0, High: 0, Medium: 0, Low: 0, Info: 0 });

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await api.get('/scans/dashboard-stats');
                const data = response.data;
                console.log(data);
                
                if (!data || !data.totalScans) {
                    console.error('Invalid or missing dashboard data:', data);
                    // Could set an empty state or error state here
                    return;
                }

                // 1. Stats from Backend
                setStats([
                    { label: 'Total Scans', value: data.totalScans.value, trend: data.totalScans.trend, icon: Activity, color: 'text-blue-500', bg: 'bg-blue-500/10' },
                    { label: 'Running Scans', value: data.runningScans.value, trend: data.runningScans.trend, icon: Server, color: 'text-purple-500', bg: 'bg-purple-500/10' },
                    { label: 'Completed', value: data.completedScans.value, trend: data.completedScans.trend, icon: CheckCircle, color: 'text-green-500', bg: 'bg-green-500/10' },
                    { label: 'Failed', value: data.failedScans.value, trend: data.failedScans.trend, icon: AlertTriangle, color: 'text-red-500', bg: 'bg-red-500/10' },
                ]);

                // 2. Trend Data from Backend
                setTrendData(data.chartData);

                // 3. Vuln Dist from Backend
                setVulnDist(data.vulnDist);

                // 4. Recent Scans from Backend
                // Backend returns top 5 with results included, so we just need to count findings for display
                // The backend doesn't pre-count finding types in the 'recentScans' list logic I wrote (it returns full scan objects).
                // So we still need a lightweight map here to show badges in the table.
                const enrichedScans = data.recentScans.map((s: any) => {
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
                setRecentScans(enrichedScans);

            } catch (error) {
                console.error('Failed to fetch dashboard data:', error);
            } finally {
                setLoading(false);
            }
        };

        // Initial fetch
        fetchData();

        const onScanUpdate = (data: any) => {
            console.log("Dashboard received update:", data);
            fetchData();
        };

        addEventListener("SCAN_UPDATE", onScanUpdate);

        return () => {
            removeEventListener("SCAN_UPDATE", onScanUpdate);
        };
    }, []);

    // Helper for Line Chart
    const LineChart = () => {
        const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
        const height = 200;
        const width = 600; // Viewbox width
        const padding = 20;
        
        const maxVal = Math.max(...trendData.map(d => d.total), 5); // Min scale 5
        
        const getX = (i: number) => (i / (trendData.length - 1)) * (width - 2 * padding) + padding;
        const getY = (val: number) => height - padding - (val / maxVal) * (height - 2 * padding);

        const pointsTotal = trendData.map((d, i) => `${getX(i)},${getY(d.total)}`).join(' ');
        const pointsCompleted = trendData.map((d, i) => `${getX(i)},${getY(d.completed)}`).join(' ');
        const pointsFailed = trendData.map((d, i) => `${getX(i)},${getY(d.failed)}`).join(' ');

        return (
            <div className="w-full h-full relative group">
                <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-visible">
                    {/* Grid Lines */}
                    {[0, 0.25, 0.5, 0.75, 1].map(p => (
                        <line 
                            key={p} 
                            x1={padding} 
                            y1={height - padding - p * (height - 2 * padding)} 
                            x2={width - padding} 
                            y2={height - padding - p * (height - 2 * padding)} 
                            className="stroke-gray-200 dark:stroke-gray-700"
                            strokeDasharray="4 4" 
                            strokeWidth="1" 
                        />
                    ))}
                    
                    {/* Lines */}
                    <polyline points={pointsTotal} fill="none" stroke="#3B82F6" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                    <polyline points={pointsCompleted} fill="none" stroke="#10B981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                    <polyline points={pointsFailed} fill="none" stroke="#EF4444" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />

                    {/* Hover Line */}
                    {hoveredIndex !== null && (
                        <line
                            x1={getX(hoveredIndex)}
                            y1={padding}
                            x2={getX(hoveredIndex)}
                            y2={height - padding}
                            className="stroke-gray-400 dark:stroke-gray-600"
                            strokeWidth="1"
                            strokeDasharray="4 4"
                        />
                    )}

                    {/* Dots */}
                    {trendData.map((d, i) => {
                        const x = getX(i);
                        const yTotal = getY(d.total);
                        const yCompleted = getY(d.completed);
                        const yFailed = getY(d.failed);
                        const isHovered = hoveredIndex === i;
                        
                        return (
                            <g key={i}>
                                <circle 
                                    cx={x} cy={yTotal} 
                                    r={isHovered ? "6" : "4"} 
                                    fill="#3B82F6" 
                                    stroke="#fff" 
                                    strokeWidth="2"
                                    className="transition-all duration-200"
                                />
                                <circle 
                                    cx={x} cy={yCompleted} 
                                    r={isHovered ? "6" : "4"} 
                                    fill="#10B981" 
                                    stroke="#fff" 
                                    strokeWidth="2"
                                    className="transition-all duration-200"
                                />
                                <circle 
                                    cx={x} cy={yFailed} 
                                    r={isHovered ? "6" : "4"} 
                                    fill="#EF4444" 
                                    stroke="#fff" 
                                    strokeWidth="2"
                                    className="transition-all duration-200"
                                />
                                {/* X Axis Labels */}
                                <text x={x} y={height} textAnchor="middle" className="fill-gray-500 dark:fill-gray-400 text-[10px]">{d.date}</text>
                            </g>
                        );
                    })}

                    {/* Invisible Hit Areas */}
                    {trendData.map((_, i) => (
                        <rect
                            key={i}
                            x={getX(i) - (width / trendData.length / 2)}
                            y={0}
                            width={width / trendData.length}
                            height={height}
                            fill="transparent"
                            onMouseEnter={() => setHoveredIndex(i)}
                            onMouseLeave={() => setHoveredIndex(null)}
                            className="cursor-crosshair"
                        />
                    ))}
                </svg>

                {/* Tooltip */}
                {hoveredIndex !== null && (
                    <div 
                        className="absolute bg-gray-800 border border-gray-700 p-3 rounded-lg shadow-xl z-10 pointer-events-none"
                        style={{ 
                            left: `${(hoveredIndex / (trendData.length - 1)) * 100}%`, 
                            top: '10%',
                            transform: 'translateX(-50%)'
                        }}
                    >
                        <p className="text-white font-bold text-sm mb-2">{trendData[hoveredIndex].date}</p>
                        <div className="space-y-1 text-xs">
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-blue-500"></div>
                                <span className="text-gray-400">Total:</span>
                                <span className="text-white font-mono ml-auto">{trendData[hoveredIndex].total}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                                <span className="text-gray-400">Completed:</span>
                                <span className="text-white font-mono ml-auto">{trendData[hoveredIndex].completed}</span>
                            </div>
                            <div className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full bg-red-500"></div>
                                <span className="text-gray-400">Failed:</span>
                                <span className="text-white font-mono ml-auto">{trendData[hoveredIndex].failed}</span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    // Helper for Donut Chart
    const DonutChart = () => {

        // Exclude Info from chart total for consistency with ScanDetails if desired, 
        // but user asked for "same card", and ScanDetails excludes Info from chart.
        // Let's check ScanDetails logic: 
        // const chartTotal = severityCounts.Critical + severityCounts.High + severityCounts.Medium + severityCounts.Low;
        // So we should probably exclude Info from the chart visualization too for exact match,
        // OR keep it if Dashboard usually shows all. 
        // The user said "make this card... look the same as in the Scan's".
        // In ScanDetails, Info is NOT in the chart.
        // Let's follow ScanDetails logic.
        
        const chartTotal = vulnDist.Critical + vulnDist.High + vulnDist.Medium + vulnDist.Low;
        const radius = 35;
        const strokeWidth = 20;
        const circumference = 2 * Math.PI * radius;
        let currentOffset = 0;

        const segments = [
            { count: vulnDist.Critical, color: '#EF4444' },
            { count: vulnDist.High, color: '#F97316' },
            { count: vulnDist.Medium, color: '#EAB308' },
            { count: vulnDist.Low, color: '#3B82F6' },
            // Info excluded from chart to match ScanDetails
        ].filter(s => s.count > 0);

        if (chartTotal === 0) return (
            <div className="relative w-32 h-32 flex items-center justify-center">
                <div className="w-24 h-24 rounded-full border-4 border-gray-800 flex items-center justify-center text-gray-600 text-xs font-medium">
                    No Issues
                </div>
            </div>
        );

        return (
            <div className="relative w-40 h-40">
                <div className="absolute inset-0 flex items-center justify-center z-10 flex-col">
                    <span className="text-3xl font-bold text-gray-900 dark:text-white leading-none">{chartTotal}</span>
                    <span className="text-xs text-gray-500 uppercase font-medium mt-1">Issues</span>
                </div>
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                    <circle cx="50" cy="50" r={radius} fill="transparent" className="stroke-gray-100 dark:stroke-gray-800" strokeWidth={strokeWidth} />
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
                                strokeLinecap="butt"
                                className="transition-all duration-1000 ease-out"
                            />
                        );
                    })}
                </svg>
            </div>
        );
    };

    if (loading) return <div className="flex justify-center items-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div></div>;

    return (
        <PageTransition className="space-y-6">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Security Dashboard</h1>
                    <p className="text-sm text-gray-500">Last updated: Just now</p>
                </div>
                <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => navigate('/scan/new')}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors shadow-lg shadow-blue-500/20"
                >
                    <Play className="w-4 h-4" />
                    Start a New Scan
                </motion.button>
            </div>

            {/* Stats Grid */}
            <motion.div 
                variants={containerVariants}
                initial="hidden"
                animate="show"
                className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
            >
                {stats.map((stat, index) => (
                    <motion.div 
                        key={index} 
                        variants={itemVariants}
                        whileHover={{ y: -5, transition: { duration: 0.2 } }}
                        className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm hover:shadow-lg transition-all"
                    >
                        <div className="flex justify-between items-start mb-4">
                            <div className={`p-3 rounded-lg ${stat.bg}`}>
                                <stat.icon className={`w-6 h-6 ${stat.color}`} />
                            </div>
                        </div>
                        <p className="text-gray-500 dark:text-gray-400 text-sm mb-1">{stat.label}</p>
                        <h3 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">{stat.value}</h3>
                        {stat.trend !== 0 && (
                            <div className={`flex items-center text-xs font-medium ${stat.trend > 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {stat.trend > 0 ? <ArrowUpRight className="w-3 h-3 mr-1" /> : <ArrowDownRight className="w-3 h-3 mr-1" />}
                                {Math.abs(stat.trend)}% vs last week
                            </div>
                        )}
                        {stat.trend === 0 && <div className="text-xs text-gray-500 dark:text-gray-600">No change vs last week</div>}
                    </motion.div>
                ))}
            </motion.div>

            {/* Charts Row */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* Scan Trends */}
                <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm">
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-1">Scan Trends</h3>
                    <p className="text-sm text-gray-500 mb-6">Last 7 days activity</p>
                    <div className="h-64">
                        <LineChart />
                    </div>
                    <div className="flex justify-center gap-6 mt-4">
                        <div className="flex items-center gap-2 text-xs text-gray-500"><div className="w-2 h-2 rounded-full bg-blue-500"></div> Total Scans</div>
                        <div className="flex items-center gap-2 text-xs text-gray-500"><div className="w-2 h-2 rounded-full bg-green-500"></div> Completed</div>
                    </div>
                </div>

                {/* Vulnerability Distribution */}
                <div className="bg-white dark:bg-gray-900 p-6 rounded-xl border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col justify-between h-full">
                    {(() => {
                        const chartTotal = vulnDist.Critical + vulnDist.High + vulnDist.Medium + vulnDist.Low;
                        const highSeverityCount = vulnDist.Critical + vulnDist.High;
                        
                        // Calculate Risk Score (Weighted Average: Critical=100, High=75, Medium=50, Low=25)
                        const totalWeightedScore = (vulnDist.Critical * 100) + (vulnDist.High * 75) + (vulnDist.Medium * 50) + (vulnDist.Low * 25);
                        const riskScore = chartTotal > 0 ? totalWeightedScore / chartTotal : 0;

                        return (
                            <>
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
                                            { label: 'Critical', count: vulnDist.Critical, color: 'bg-red-500', text: 'text-red-500' },
                                            { label: 'High', count: vulnDist.High, color: 'bg-orange-500', text: 'text-orange-500' },
                                            { label: 'Medium', count: vulnDist.Medium, color: 'bg-yellow-500', text: 'text-yellow-500' },
                                            { label: 'Low', count: vulnDist.Low, color: 'bg-blue-500', text: 'text-blue-500' }
                                        ].map((item) => (
                                            <div key={item.label} className="flex items-center justify-between text-sm">
                                                <div className="flex items-center gap-2">
                                                    <div className={`w-2.5 h-2.5 rounded-full ${item.color}`}></div>
                                                    <span className="text-gray-300">{item.label}</span>
                                                </div>
                                                <div className="flex items-center gap-4">
                                                    <span className={`${item.count > 0 ? item.text : 'text-gray-500'} font-medium`}>{item.count}</span>
                                                    <span className="text-gray-600 w-12 text-right">
                                                        {chartTotal > 0 ? ((item.count / chartTotal) * 100).toFixed(1) : '0.0'}%
                                                    </span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Footer Stats */}
                                <div className="grid grid-cols-2 gap-4 pt-6 border-t border-gray-800">
                                    <div>
                                        <p className="text-xs text-gray-500 uppercase font-medium mb-1">High Priority</p>
                                        <p className={`text-2xl font-bold ${highSeverityCount > 0 ? 'text-orange-500' : 'text-gray-400'}`}>
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
                                            <span className="text-sm text-gray-500">/100</span>
                                        </div>
                                    </div>
                                </div>
                            </>
                        );
                    })()}
                </div>
            </div>

            {/* Recent Scans Table */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden shadow-sm">
                <div className="p-6 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center">
                    <div>
                        <h3 className="text-lg font-bold text-gray-900 dark:text-white">Recent Scans</h3>
                        <p className="text-sm text-gray-500">Latest security scan results</p>
                    </div>
                    <button onClick={() => navigate('/scan/history')} className="text-sm text-blue-600 dark:text-blue-500 hover:text-blue-500 dark:hover:text-blue-400">View all scans →</button>
                </div>
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
                            {recentScans.map((scan) => (
                                <tr key={scan.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
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
                                        <div className="flex items-center gap-3 text-xs font-mono">
                                            <span className="text-red-600 dark:text-red-500">C:{scan.findings.Critical}</span>
                                            <span className="text-orange-600 dark:text-orange-500">H:{scan.findings.High}</span>
                                            <span className="text-yellow-600 dark:text-yellow-500">M:{scan.findings.Medium}</span>
                                            <span className="text-blue-600 dark:text-blue-500">L:{scan.findings.Low}</span>
                                        </div>
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
                                                // Use earliest tool start time, fallback to scan creation date
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
                                        <button 
                                            onClick={() => navigate(`/scan/${scan.id}`)}
                                            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
                                        >
                                            <Eye className="w-4 h-4" />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {recentScans.length === 0 && (
                                <tr>
                                    <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                                        No scans found. Start your first scan!
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>
        </PageTransition>
    );
};

export default Dashboard;
