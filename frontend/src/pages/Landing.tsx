import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
    Shield, Search, Activity, FileText, Zap, Sparkles,
    Target, ServerCog, Brain, CheckCircle, ArrowRight, 
    Star, Code2, Moon, Sun, ChevronDown, Users,
    TrendingUp, Rocket, BarChart, CheckCircle2
} from 'lucide-react';
import { useState, useEffect } from 'react';

const Landing = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { theme, toggleTheme } = useTheme();
    const { scrollY } = useScroll();
    const [hoveredFeature, setHoveredFeature] = useState<number | null>(null);
    const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
    const [openFaq, setOpenFaq] = useState<number | null>(null);
    
    // Optimized cursor tracking with RequestAnimationFrame for 60fps smooth updates
    useEffect(() => {
        let mouseX = 0;
        let mouseY = 0;
        let rafId: number;

        const handleMouseMove = (e: MouseEvent) => {
            mouseX = e.clientX;
            mouseY = e.clientY;
        };

        const updateMousePosition = () => {
            setMousePosition({ x: mouseX, y: mouseY });
            rafId = requestAnimationFrame(updateMousePosition);
        };
        
        window.addEventListener('mousemove', handleMouseMove);
        rafId = requestAnimationFrame(updateMousePosition);
        
        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            cancelAnimationFrame(rafId);
        };
    }, []);
    
    // Parallax effect for background
    const y1 = useTransform(scrollY, [0, 300], [0, 100]);
    const y2 = useTransform(scrollY, [0, 300], [0, -100]);

    const handleGetStarted = () => {
        if (user) {
            navigate('/dashboard');
        } else {
            navigate('/register');
        }
    };

    const handleSignIn = () => {
        if (user) {
            navigate('/dashboard');
        } else {
            navigate('/login');
        }
    };

    const features = [
        {
            icon: Search,
            title: 'Multi-Phase Reconnaissance',
            description: 'Advanced passive & active recon to gather intelligence stealthily',
            color: 'from-blue-500 to-cyan-500',
            iconColor: 'text-blue-500',
            bgHover: 'group-hover:bg-blue-500/5'
        },
        {
            icon: Target,
            title: 'Asset Discovery',
            description: 'Automated discovery of subdomains, endpoints, and attack surfaces',
            color: 'from-purple-500 to-pink-500',
            iconColor: 'text-purple-500',
            bgHover: 'group-hover:bg-purple-500/5'
        },
        {
            icon: ServerCog,
            title: '15+ Security Tools',
            description: 'Nmap, Nuclei, SQLMap, FFUF, Subfinder, and many more integrated',
            color: 'from-green-500 to-emerald-500',
            iconColor: 'text-green-500',
            bgHover: 'group-hover:bg-green-500/5'
        },
        {
            icon: Brain,
            title: 'AI-Powered Analysis',
            description: 'Gemini AI identifies vulnerabilities with intelligent context',
            color: 'from-orange-500 to-red-500',
            iconColor: 'text-orange-500',
            bgHover: 'group-hover:bg-orange-500/5'
        },
        {
            icon: Activity,
            title: 'Real-Time Monitoring',
            description: 'Live output streaming and progress tracking for all scans',
            color: 'from-red-500 to-rose-500',
            iconColor: 'text-red-500',
            bgHover: 'group-hover:bg-red-500/5'
        },
        {
            icon: FileText,
            title: 'Professional Reports',
            description: 'Auto-generated PDF reports with detailed actionable insights',
            color: 'from-yellow-500 to-amber-500',
            iconColor: 'text-yellow-500',
            bgHover: 'group-hover:bg-yellow-500/5'
        }
    ];

    const tools = [
        'Nmap', 'Nuclei', 'SQLMap', 'Dalfox', 'FFUF', 'Subfinder',
        'WhatWeb', 'WafW00f', 'SSLScan', 'Amass', 'Assetfinder',
        'NSLookup', 'Whois', 'DNS Resolver', 'Web Scraper'
    ];

    const scanPhases = [
        { name: 'Passive Recon', icon: Search },
        { name: 'Active Recon', icon: Target },
        { name: 'Asset Discovery', icon: Sparkles },
        { name: 'Enumeration', icon: Code2 },
        { name: 'Vulnerability Analysis', icon: Shield }
    ];

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-[#0B1120] text-gray-900 dark:text-white transition-colors duration-300 overflow-hidden">
            {/* Cursor Glow Effect - GPU Accelerated */}
            <div
                className="fixed inset-0 pointer-events-none z-30"
                style={{
                    background: `radial-gradient(600px circle at ${mousePosition.x}px ${mousePosition.y}px, rgba(59, 130, 246, 0.15), transparent 40%)`,
                    willChange: 'background',
                }}
            />
            
            {/* Animated Background Elements */}
            <div className="fixed inset-0 pointer-events-none">
                <motion.div
                    style={{ y: y1 }}
                    className="absolute top-20 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl"
                    transition={{ type: "spring", stiffness: 50, damping: 20 }}
                />
                <motion.div
                    style={{ y: y2 }}
                    className="absolute top-40 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl"
                    transition={{ type: "spring", stiffness: 50, damping: 20 }}
                />
                <motion.div
                    style={{ y: y1 }}
                    className="absolute bottom-20 left-1/3 w-96 h-96 bg-pink-500/10 rounded-full blur-3xl"
                />
            </div>

            {/* Navigation */}
            <motion.nav
                initial={{ y: -100 }}
                animate={{ y: 0 }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className="fixed top-0 left-0 right-0 z-50 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200 dark:border-gray-800"
            >
                <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
                    <motion.div
                        whileHover={{ scale: 1.05 }}
                        className="flex items-center gap-3 cursor-pointer"
                        onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
                    >
                        <div className="p-2 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl shadow-lg shadow-blue-500/30">
                            <Shield className="w-6 h-6 text-white fill-current" />
                        </div>
                        <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Scout</span>
                    </motion.div>

                    <div className="flex items-center gap-4">
                        {/* Theme Toggle Button */}
                        <motion.button
                            whileHover={{ scale: 1.1, rotate: 180 }}
                            whileTap={{ scale: 0.9 }}
                            onClick={toggleTheme}
                            className="p-2 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                            aria-label="Toggle theme"
                        >
                            <motion.div
                                initial={false}
                                animate={{ rotate: theme === 'dark' ? 0 : 180, scale: theme === 'dark' ? 1 : 0 }}
                                transition={{ duration: 0.3 }}
                                className="absolute"
                            >
                                <Moon className="w-5 h-5 text-gray-700 dark:text-gray-300" />
                            </motion.div>
                            <motion.div
                                initial={false}
                                animate={{ rotate: theme === 'light' ? 0 : 180, scale: theme === 'light' ? 1 : 0 }}
                                transition={{ duration: 0.3 }}
                            >
                                <Sun className="w-5 h-5 text-gray-700 dark:text-gray-300" />
                            </motion.div>
                        </motion.button>

                        <motion.button
                            whileHover={{ scale: 1.05 }}
                            whileTap={{ scale: 0.95 }}
                            onClick={handleSignIn}
                            className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
                        >
                            Sign In
                        </motion.button>
                        <motion.button
                            whileHover={{ scale: 1.05, boxShadow: "0 20px 40px rgba(59, 130, 246, 0.4)" }}
                            whileTap={{ scale: 0.95 }}
                            onClick={handleGetStarted}
                            className="px-5 py-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-sm font-bold rounded-lg shadow-lg shadow-blue-500/30 transition-all"
                        >
                            Get Started
                        </motion.button>
                    </div>
                </div>
            </motion.nav>

            {/* Hero Section */}
            <section className="relative pt-32 pb-24 px-6">
                <div className="max-w-6xl mx-auto text-center relative z-10">
                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.1 }}
                    >
                        <motion.div
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            transition={{ type: "spring", stiffness: 150, damping: 12, delay: 0.2 }}
                            className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-full text-blue-600 dark:text-blue-400 text-sm font-medium mb-8"
                        >
                            <Sparkles className="w-4 h-4" />
                            AI-Powered Security Testing Platform
                        </motion.div>

                        <motion.h1
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.3 }}
                            className="text-5xl md:text-6xl lg:text-7xl font-black mb-6 leading-tight"
                        >
                            <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 bg-clip-text text-transparent animate-gradient">
                                Enterprise-Grade
                            </span>
                            <br />
                            <span className="text-gray-900 dark:text-white">Security Scanning</span>
                        </motion.h1>

                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ type: "spring", stiffness: 100, damping: 20, delay: 0.4 }}
                            className="text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto mb-10 leading-relaxed"
                        >
                            Comprehensive penetration testing with <span className="font-bold text-blue-600 dark:text-blue-400">15+ integrated tools</span>, 
                            real-time monitoring, and <span className="font-bold text-purple-600 dark:text-purple-400">AI-powered analysis</span>—all in one platform.
                        </motion.p>

                        <motion.div
                            initial={{ opacity: 0, y: 20 }}
                            animate={{ opacity: 1, y: 0 }}
                            transition={{ type: "spring", stiffness: 100, damping: 15, delay: 0.5 }}
                            className="flex flex-col sm:flex-row items-center justify-center gap-4"
                        >
                            <motion.button
                                whileHover={{ scale: 1.05, boxShadow: "0 20px 40px rgba(59, 130, 246, 0.4)" }}
                                whileTap={{ scale: 0.95 }}
                                transition={{ type: "spring", stiffness: 400, damping: 17 }}
                                onClick={handleGetStarted}
                                className="group px-8 py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-bold rounded-xl shadow-2xl shadow-blue-500/40 transition-all flex items-center gap-2"
                            >
                                <Zap className="w-5 h-5 fill-current" />
                                Start Scanning Now
                                <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                            </motion.button>
                            <motion.button
                                whileHover={{ scale: 1.05, borderColor: "rgb(147, 51, 234)" }}
                                whileTap={{ scale: 0.95 }}
                                transition={{ type: "spring", stiffness: 400, damping: 17 }}
                                onClick={() => document.getElementById('features')?.scrollIntoView({ behavior: 'smooth' })}
                                className="px-8 py-4 bg-white dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-800 text-gray-900 dark:text-white font-medium rounded-xl hover:border-purple-500 dark:hover:border-purple-500 transition-all"
                            >
                                Explore Features
                            </motion.button>
                        </motion.div>

                        {/* Floating Indicators */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ duration: 1, delay: 1 }}
                            className="flex items-center justify-center gap-8 mt-16"
                        >
                            {scanPhases.map((phase, idx) => (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.5, delay: 1 + idx * 0.1 }}
                                    whileHover={{ y: -5 }}
                                    className="hidden md:flex flex-col items-center gap-2 cursor-default"
                                >
                                    <div className="p-3 bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg">
                                        <phase.icon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                    </div>
                                    <span className="text-xs text-gray-500 dark:text-gray-400 font-medium">{phase.name}</span>
                                </motion.div>
                            ))}
                        </motion.div>
                    </motion.div>
                </div>
            </section>

            {/* Features Section */}
            <section id="features" className="py-20 px-6 bg-white/50 dark:bg-gray-900/30 backdrop-blur-sm relative">
                <div className="max-w-6xl mx-auto relative z-10">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                                Everything You Need
                            </span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            Professional-grade penetration testing with intelligent automation
                        </p>
                    </motion.div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {features.map((feature, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 30 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                whileHover={{ y: -10, scale: 1.02 }}
                                onHoverStart={() => setHoveredFeature(index)}
                                onHoverEnd={() => setHoveredFeature(null)}
                                className={`group relative bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-8 hover:border-transparent hover:shadow-2xl transition-all duration-300 cursor-default ${feature.bgHover}`}
                            >
                                {/* Gradient Border on Hover */}
                                <div className={`absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r ${feature.color} p-[2px]`}>
                                    <div className="w-full h-full bg-white dark:bg-gray-900 rounded-2xl"></div>
                                </div>

                                <div className="relative z-10">
                                    <motion.div
                                        animate={{
                                            rotate: hoveredFeature === index ? [0, -10, 10, -10, 0] : 0,
                                            scale: hoveredFeature === index ? 1.1 : 1
                                        }}
                                        transition={{ duration: 0.5 }}
                                        className={`inline-flex p-4 rounded-xl bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 mb-5 group-hover:shadow-lg transition-all`}
                                    >
                                        <feature.icon className={`w-7 h-7 ${feature.iconColor}`} />
                                    </motion.div>
                                    
                                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3 group-hover:bg-gradient-to-r group-hover:from-blue-600 group-hover:to-purple-600 group-hover:bg-clip-text group-hover:text-transparent transition-all">
                                        {feature.title}
                                    </h3>
                                    
                                    <p className="text-gray-600 dark:text-gray-400 leading-relaxed">
                                        {feature.description}
                                    </p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* How It Works Section */}
            <section className="py-20 px-6 relative">
                <div className="max-w-6xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            How <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Scout Works</span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            From target to report in 4 simple steps
                        </p>
                    </motion.div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                        {[
                            { icon: Target, title: 'Enter Target', description: 'Input your target URL or IP address', step: '01' },
                            { icon: Rocket, title: 'Select Phases', description: 'Choose from 5 comprehensive scan phases', step: '02' },
                            { icon: Brain, title: 'AI Analysis', description: 'Gemini AI analyzes results in real-time', step: '03' },
                            { icon: FileText, title: 'Get Report', description: 'Download professional PDF report', step: '04' }
                        ].map((item, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 30 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                whileHover={{ y: -5 }}
                                className="relative text-center group"
                            >
                                {/* Connecting Line */}
                                {index < 3 && (
                                    <div className="hidden lg:block absolute top-12 left-full w-full h-0.5 bg-gradient-to-r from-blue-500/50 to-purple-500/50 -z-10" />
                                )}
                                
                                {/* Step Number - Prominent Badge */}
                                <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                                    <div className="w-8 h-8 rounded-full bg-gradient-to-r from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-sm shadow-lg">
                                        {index + 1}
                                    </div>
                                </div>

                                <div className="relative bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-8 hover:border-blue-500 dark:hover:border-blue-500 hover:shadow-xl transition-all">
                                    <motion.div
                                        whileHover={{ rotate: 360 }}
                                        transition={{ duration: 0.6 }}
                                        className="inline-flex p-4 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 mb-6 shadow-lg shadow-blue-500/30"
                                    >
                                        <item.icon className="w-8 h-8 text-white" />
                                    </motion.div>
                                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">{item.title}</h3>
                                    <p className="text-gray-600 dark:text-gray-400">{item.description}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>

                </div>
            </section>

            {/* Product Preview Section */}
            <section className="py-20 px-6 bg-white/50 dark:bg-gray-900/30 backdrop-blur-sm">
                <div className="max-w-6xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            <span className="bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                                Dashboard Preview
                            </span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            Your security command center with real-time insights
                        </p>
                    </motion.div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.8 }}
                        className="relative rounded-3xl overflow-hidden border border-gray-200 dark:border-gray-800 shadow-2xl"
                    >
                        {/* Realistic Dashboard Mockup */}
                        <div className="bg-gradient-to-br from-blue-600 via-purple-600 to-pink-600 p-1">
                            <div className="w-full bg-[#0B1120] rounded-2xl flex overflow-hidden" style={{ minHeight: '500px' }}>
                                {/* Sidebar */}
                                <div className="w-40 bg-[#0f172a] border-r border-gray-800 p-3 hidden md:flex flex-col flex-shrink-0">
                                    <div className="flex items-center gap-2 mb-6">
                                        <div className="p-1 bg-gradient-to-br from-blue-600 to-purple-600 rounded-lg">
                                            <Shield className="w-3 h-3 text-white" />
                                        </div>
                                        <span className="font-bold text-white text-sm">Scout</span>
                                    </div>
                                    <div className="space-y-1">
                                        <div className="flex items-center gap-2 px-2 py-1.5 bg-blue-600/20 rounded-lg text-blue-400 text-xs">
                                            <BarChart className="w-3 h-3" />
                                            <span>Dashboard</span>
                                        </div>
                                        <div className="flex items-center gap-2 px-2 py-1.5 text-gray-500 text-xs">
                                            <Target className="w-3 h-3" />
                                            <span>New Scan</span>
                                        </div>
                                        <div className="flex items-center gap-2 px-2 py-1.5 text-gray-500 text-xs">
                                            <FileText className="w-3 h-3" />
                                            <span>Scan History</span>
                                        </div>
                                    </div>
                                </div>

                                {/* Main Content */}
                                <div className="flex-1 p-4 overflow-hidden">
                                    {/* Header */}
                                    <div className="flex items-center justify-between mb-4">
                                        <div>
                                            <h3 className="text-sm font-bold text-white">Security Dashboard</h3>
                                            <p className="text-xs text-gray-500">Last updated: Just now</p>
                                        </div>
                                        <div className="px-2 py-1 bg-blue-600 rounded-lg text-white text-xs font-semibold flex items-center gap-1">
                                            <Zap className="w-3 h-3" />
                                            Start a New Scan
                                        </div>
                                    </div>

                                    {/* Stats Cards */}
                                    <div className="grid grid-cols-4 gap-2 mb-4">
                                        <div className="bg-[#1e293b] rounded-lg p-2">
                                            <div className="flex items-center gap-1 mb-1">
                                                <Activity className="w-3 h-3 text-blue-500" />
                                                <span className="text-xs text-gray-400">Total Scans</span>
                                            </div>
                                            <div className="text-lg font-bold text-white">136</div>
                                            <div className="text-xs text-green-500">↑ 100%</div>
                                        </div>
                                        <div className="bg-[#1e293b] rounded-lg p-2">
                                            <div className="flex items-center gap-1 mb-1">
                                                <FileText className="w-3 h-3 text-blue-500" />
                                                <span className="text-xs text-gray-400">Running</span>
                                            </div>
                                            <div className="text-lg font-bold text-white">0</div>
                                            <div className="text-xs text-gray-500">No change</div>
                                        </div>
                                        <div className="bg-[#1e293b] rounded-lg p-2">
                                            <div className="flex items-center gap-1 mb-1">
                                                <CheckCircle className="w-3 h-3 text-green-500" />
                                                <span className="text-xs text-gray-400">Completed</span>
                                            </div>
                                            <div className="text-lg font-bold text-white">114</div>
                                            <div className="text-xs text-green-500">↑ 100%</div>
                                        </div>
                                        <div className="bg-[#1e293b] rounded-lg p-2">
                                            <div className="flex items-center gap-1 mb-1">
                                                <Shield className="w-3 h-3 text-red-500" />
                                                <span className="text-xs text-gray-400">Failed</span>
                                            </div>
                                            <div className="text-lg font-bold text-white">12</div>
                                            <div className="text-xs text-gray-500">No change</div>
                                        </div>
                                    </div>

                                    {/* Charts Row */}
                                    <div className="grid grid-cols-2 gap-3 mb-4">
                                        {/* Scan Trends */}
                                        <div className="bg-[#1e293b] rounded-lg p-3">
                                            <h4 className="text-xs font-semibold text-white mb-1">Scan Trends</h4>
                                            <p className="text-xs text-gray-500 mb-2">Last 7 days</p>
                                            <div className="h-12 flex items-end gap-1">
                                                {[20, 35, 25, 40, 30, 45, 50].map((h, i) => (
                                                    <div key={i} className="flex-1 bg-gradient-to-t from-blue-600 to-blue-400 rounded-t" style={{ height: `${h}%` }} />
                                                ))}
                                            </div>
                                        </div>

                                        {/* Vulnerability Distribution */}
                                        <div className="bg-[#1e293b] rounded-lg p-3">
                                            <div className="flex items-center justify-between mb-2">
                                                <h4 className="text-xs font-semibold text-white">Vulnerability Distribution</h4>
                                                <span className="text-xs bg-gray-800 px-1.5 py-0.5 rounded text-gray-400">946</span>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <div className="w-12 h-12 rounded-full border-4 border-yellow-500 border-t-red-500 border-r-orange-500 border-b-blue-500 flex items-center justify-center">
                                                    <span className="text-xs font-bold text-white">946</span>
                                                </div>
                                                <div className="space-y-0.5 text-xs">
                                                    <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 bg-red-500 rounded-full" /><span className="text-gray-400">Critical: 5</span></div>
                                                    <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 bg-orange-500 rounded-full" /><span className="text-gray-400">High: 90</span></div>
                                                    <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 bg-yellow-500 rounded-full" /><span className="text-gray-400">Medium: 463</span></div>
                                                    <div className="flex items-center gap-1"><div className="w-1.5 h-1.5 bg-blue-500 rounded-full" /><span className="text-gray-400">Low: 388</span></div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Recent Scans Table */}
                                    <div className="bg-[#1e293b] rounded-lg p-3">
                                        <div className="flex items-center justify-between mb-3">
                                            <div>
                                                <h4 className="text-xs font-semibold text-white">Recent Scans</h4>
                                                <p className="text-xs text-gray-500">Latest security scan results</p>
                                            </div>
                                            <span className="text-xs text-blue-400">View all scans →</span>
                                        </div>
                                        <div className="space-y-2">
                                            {/* Table Header */}
                                            <div className="grid grid-cols-5 gap-2 text-xs text-gray-500 pb-1 border-b border-gray-700">
                                                <span>SCAN ID</span>
                                                <span>TARGET</span>
                                                <span>STATUS</span>
                                                <span>FINDINGS</span>
                                                <span>TIME</span>
                                            </div>
                                            {/* Table Rows */}
                                            {[
                                                { id: '#144', target: 'sarral.io', status: 'Completed', findings: 'C:0 H:0 M:3 L:0', time: '15/12/2025' },
                                                { id: '#143', target: 'sarral.io', status: 'Completed', findings: 'C:0 H:0 M:3 L:0', time: '15/12/2025' },
                                                { id: '#142', target: 'sarral.io', status: 'Completed', findings: 'C:0 H:0 M:3 L:0', time: '15/12/2025' }
                                            ].map((scan, i) => (
                                                <div key={i} className="grid grid-cols-5 gap-2 text-xs py-1">
                                                    <span className="text-blue-400">{scan.id}</span>
                                                    <span className="text-white">{scan.target}</span>
                                                    <span className="text-green-500 flex items-center gap-1">
                                                        <CheckCircle className="w-2.5 h-2.5" />
                                                        {scan.status}
                                                    </span>
                                                    <span className="text-gray-400 font-mono text-xs">
                                                        <span className="text-red-400">C:0</span> <span className="text-orange-400">H:0</span> <span className="text-yellow-400">M:3</span> <span className="text-blue-400">L:0</span>
                                                    </span>
                                                    <span className="text-gray-400">{scan.time}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* Use Cases Section */}
            <section className="py-20 px-6">
                <div className="max-w-6xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            Built For <span className="bg-gradient-to-r from-green-600 to-teal-600 bg-clip-text text-transparent">Every Team</span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            Trusted by security professionals across industries
                        </p>
                    </motion.div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                        {[
                            { icon: Shield, title: 'Security Teams', description: 'Comprehensive vulnerability assessments', gradient: 'from-blue-500 to-cyan-500' },
                            { icon: Users, title: 'Pen Testers', description: 'Automated reconnaissance and scanning', gradient: 'from-purple-500 to-pink-500' },
                            { icon: ServerCog, title: 'Enterprises', description: 'Scale security across infrastructure', gradient: 'from-green-500 to-emerald-500' },
                            { icon: Code2, title: 'DevSecOps', description: 'Integrate security into CI/CD', gradient: 'from-orange-500 to-red-500' }
                        ].map((useCase, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 30 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.5, delay: index * 0.1 }}
                                whileHover={{ y: -5, scale: 1.02 }}
                                className="relative group"
                            >
                                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-8 hover:border-transparent hover:shadow-2xl transition-all h-full">
                                    <div className={`absolute inset-0 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 bg-gradient-to-r ${useCase.gradient} p-[2px]`}>
                                        <div className="w-full h-full bg-white dark:bg-gray-900 rounded-2xl"></div>
                                    </div>
                                    
                                    <div className="relative z-10">
                                        <div className={`inline-flex p-4 rounded-xl bg-gradient-to-br ${useCase.gradient} mb-5 shadow-lg`}>
                                            <useCase.icon className="w-7 h-7 text-white" />
                                        </div>
                                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-3">{useCase.title}</h3>
                                        <p className="text-gray-600 dark:text-gray-400">{useCase.description}</p>
                                    </div>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* Benefits/Comparison Section */}
            <section className="py-20 px-6 bg-white/50 dark:bg-gray-900/30 backdrop-blur-sm">
                <div className="max-w-6xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                           Why Choose <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Scout?</span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            The smart alternative to manual security testing
                        </p>
                    </motion.div>

                    <div className="grid md:grid-cols-2 gap-8">
                        {/* Manual Testing */}
                        <motion.div
                            initial={{ opacity: 0, x: -50 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.6 }}
                            className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-8"
                        >
                            <div className="flex items-center gap-3 mb-6">
                                <div className="p-3 bg-red-500/10 rounded-lg">
                                    <BarChart className="w-6 h-6 text-red-500" />
                                </div>
                                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">Manual Testing</h3>
                            </div>
                            <div className="space-y-4">
                                {[
                                    'Hours of manual setup',
                                    'Inconsistent results',
                                    'Limited tool coverage',
                                    'Human error prone',
                                    'No AI insights'
                                ].map((item, idx) => (
                                    <div key={idx} className="flex items-start gap-3">
                                        <div className="mt-1 p-0.5 rounded-full bg-red-500/20">
                                            <div className="w-2 h-2 bg-red-500 rounded-full" />
                                        </div>
                                        <span className="text-gray-600 dark:text-gray-400">{item}</span>
                                    </div>
                                ))}
                            </div>
                        </motion.div>

                        {/* Scout */}
                        <motion.div
                            initial={{ opacity: 0, x: 50 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.6 }}
                            className="bg-gradient-to-br from-blue-500 to-purple-600 border border-blue-500 rounded-2xl p-8 relative overflow-hidden"
                        >
                            <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-white/10 rounded-full blur-2xl" />
                            <div className="relative z-10">
                                <div className="flex items-center gap-3 mb-6">
                                    <div className="p-3 bg-white/20 backdrop-blur-sm rounded-lg">
                                        <TrendingUp className="w-6 h-6 text-white" />
                                    </div>
                                    <h3 className="text-2xl font-bold text-white">Scout Automated</h3>
                                </div>
                                <div className="space-y-4">
                                    {[
                                        { text: 'Faster automation', highlight: 'Faster' },
                                        { text: 'Consistent, reliable results', highlight: 'Consistent' },
                                        { text: '15+ integrated tools', highlight: '15+ tools' },
                                        { text: 'Minimal errors vs manual testing', highlight: 'Minimal errors' },
                                        { text: 'AI-powered insights', highlight: 'AI-powered' }
                                    ].map((item, idx) => (
                                        <motion.div
                                            key={idx}
                                            initial={{ opacity: 0, x: 20 }}
                                            whileInView={{ opacity: 1, x: 0 }}
                                            viewport={{ once: true }}
                                            transition={{ duration: 0.4, delay: idx * 0.1 }}
                                            className="flex items-start gap-3"
                                        >
                                            <CheckCircle2 className="w-5 h-5 text-white mt-0.5 flex-shrink-0" />
                                            <span className="text-white font-medium">{item.text}</span>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>
                        </motion.div>
                    </div>

                    {/* Key Metrics */}
                    <motion.div
                        initial={{ opacity: 0, y: 30 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.3 }}
                        className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-12"
                    >
                        {[
                            { value: '15+', label: 'Security Tools', icon: ServerCog },
                            { value: '100%', label: 'Automated', icon: Rocket },
                            { value: '5', label: 'Scan Phases', icon: Target },
                            { value: 'AI', label: 'Powered Analysis', icon: Brain }
                        ].map((metric, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, scale: 0.9 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.4, delay: 0.4 + idx * 0.1 }}
                                whileHover={{ scale: 1.05 }}
                                className="text-center bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-6"
                            >
                                <metric.icon className="w-8 h-8 text-blue-600 dark:text-blue-500 mx-auto mb-3" />
                                <div className="text-3xl font-black bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
                                    {metric.value}
                                </div>
                                <div className="text-sm text-gray-600 dark:text-gray-400">{metric.label}</div>
                            </motion.div>
                        ))}
                    </motion.div>
                </div>
            </section>

            {/* Tools Showcase */}
            <section className="py-20 px-6 relative">
                <div className="max-w-6xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-12"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            Powered By <span className="bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">Industry Leaders</span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            15+ battle-tested security tools integrated seamlessly
                        </p>
                    </motion.div>

                    <div className="flex flex-wrap justify-center gap-3 mb-16">
                        {tools.map((tool, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, scale: 0.8 }}
                                whileInView={{ opacity: 1, scale: 1 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.4, delay: index * 0.04 }}
                                whileHover={{ scale: 1.1, y: -5 }}
                                className="group relative px-5 py-3 bg-white dark:bg-gray-900 border-2 border-gray-200 dark:border-gray-800 rounded-xl text-sm font-mono text-gray-700 dark:text-gray-300 hover:border-blue-500 dark:hover:border-blue-500 hover:shadow-lg transition-all cursor-default"
                            >
                                <span className="relative z-10 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                    {tool}
                                </span>
                                <Star className="absolute top-1 right-1 w-3 h-3 text-yellow-500 opacity-0 group-hover:opacity-100 transition-opacity" />
                            </motion.div>
                        ))}
                    </div>

                    <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="relative bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 rounded-3xl p-1"
                    >
                        <div className="bg-white dark:bg-gray-900 rounded-[22px] p-10 text-center">
                            <h3 className="text-3xl font-bold mb-4 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                                Complete Scan Workflow
                            </h3>
                            <div className="flex flex-wrap items-center justify-center gap-3 mb-6">
                                {scanPhases.map((phase, idx) => (
                                    <motion.div
                                        key={idx}
                                        initial={{ opacity: 0, x: -20 }}
                                        whileInView={{ opacity: 1, x: 0 }}
                                        viewport={{ once: true }}
                                        transition={{ duration: 0.4, delay: idx * 0.1 }}
                                        className="flex items-center gap-2"
                                    >
                                        <div className="px-4 py-2 bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/20 rounded-lg">
                                            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">{phase.name}</span>
                                        </div>
                                        {idx < scanPhases.length - 1 && <ArrowRight className="w-4 h-4 text-gray-400" />}
                                    </motion.div>
                                ))}
                            </div>
                            <div className="flex items-center justify-center gap-2 text-sm text-green-600 dark:text-green-500">
                                <CheckCircle className="w-5 h-5" />
                                <span className="font-semibold">Fully automated and customizable</span>
                            </div>
                        </div>
                    </motion.div>
                </div>
            </section>

            {/* FAQ Section */}
            <section className="py-20 px-6">
                <div className="max-w-4xl mx-auto">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className="text-center mb-16"
                    >
                        <h2 className="text-4xl md:text-5xl font-bold mb-4">
                            Frequently <span className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Asked Questions</span>
                        </h2>
                        <p className="text-gray-600 dark:text-gray-400 max-w-2xl mx-auto text-lg">
                            Everything you need to know about Scout
                        </p>
                    </motion.div>

                    <div className="space-y-4">
                        {[
                            {
                                question: "What types of scans does Scout support?",
                                answer: "Scout supports 5 comprehensive scan phases: Passive Reconnaissance, Active Reconnaissance, Asset Discovery, Enumeration, and Vulnerability Analysis. Each phase can be customized based on your security requirements."
                            },
                            {
                                question: "How long does a typical scan take?",
                                answer: "Average scan time is between 15-25 minutes, depending on the target's complexity and the scan phases selected. Real-time progress tracking keeps you updated throughout the process."
                            },
                            {
                                question: "Is my data secure?",
                                answer: "Absolutely. All scan data is encrypted at rest and in transit. Scan results are stored securely and accessible only by your authenticated account. We follow industry-standard security practices to protect your data."
                            },
                            {
                                question: "Can I customize scan parameters?",
                                answer: "Yes! Scout offers full customization of scan phases, tools selection, and parameters. You can choose specific security tools from our 15+ integrated options and configure them according to your needs."
                            },
                            {
                                question: "What kind of reports does Scout generate?",
                                answer: "Scout automatically generates professional PDF reports with detailed findings, vulnerability assessments, severity ratings, and actionable recommendations. The AI-powered analysis provides contextual insights for each finding."
                            },
                            {
                                question: "How does the AI analysis work?",
                                answer: "Scout uses Gemini AI to automatically analyze scan results in real-time. The AI identifies vulnerabilities, assesses their severity, provides context about potential exploits, and suggests remediation steps—all without manual intervention."
                            }
                        ].map((faq, index) => (
                            <motion.div
                                key={index}
                                initial={{ opacity: 0, y: 20 }}
                                whileInView={{ opacity: 1, y: 0 }}
                                viewport={{ once: true }}
                                transition={{ duration: 0.4, delay: index * 0.1 }}
                                className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden hover:border-blue-500 dark:hover:border-blue-500 transition-all"
                            >
                                <button
                                    onClick={() => setOpenFaq(openFaq === index ? null : index)}
                                    className="w-full p-6 text-left flex items-center justify-between gap-4 group"
                                >
                                    <h3 className="text-lg font-bold text-gray-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                        {faq.question}
                                    </h3>
                                    <motion.div
                                        animate={{ rotate: openFaq === index ? 180 : 0 }}
                                        transition={{ duration: 0.3 }}
                                        className="flex-shrink-0"
                                    >
                                        <ChevronDown className="w-5 h-5 text-gray-500 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors" />
                                    </motion.div>
                                </button>
                                <motion.div
                                    initial={{ height: 0 }}
                                    animate={{
                                        height: openFaq === index ? "auto" : 0,
                                        opacity: openFaq === index ? 1 : 0
                                    }}
                                    transition={{ duration: 0.3 }}
                                    className="overflow-hidden"
                                >
                                    <div className="px-6 pb-6 text-gray-600 dark:text-gray-400 leading-relaxed">
                                        {faq.answer}
                                    </div>
                                </motion.div>
                            </motion.div>
                        ))}
                    </div>

                    {/* Still have questions CTA */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        whileInView={{ opacity: 1 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.4 }}
                        className="mt-12 text-center"
                    >
                        <p className="text-gray-600 dark:text-gray-400 mb-4">Still have questions?</p>
                        <button
                            onClick={handleGetStarted}
                            className="px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-semibold rounded-lg shadow-lg shadow-blue-500/30 transition-all"
                        >
                            Get Started & Explore
                        </button>
                    </motion.div>
                </div>
            </section>

            {/* CTA Section */}
            <section className="relative py-24 px-6 overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-r from-blue-600 via-purple-600 to-pink-600 opacity-90"></div>
                <motion.div
                    initial={{ opacity: 0, y: 30 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.8 }}
                    className="max-w-4xl mx-auto text-center text-white relative z-10"
                >
                    <h2 className="text-4xl md:text-5xl font-black mb-6">Ready to Fortify Your Security?</h2>
                    <p className="text-blue-100 text-xl mb-10 max-w-2xl mx-auto">
                        Join security professionals using Scout to discover vulnerabilities before attackers do
                    </p>
                    <motion.button
                        whileHover={{ scale: 1.05, boxShadow: "0 30px 60px rgba(0, 0, 0, 0.3)" }}
                        whileTap={{ scale: 0.95 }}
                        onClick={handleGetStarted}
                        className="px-10 py-5 bg-white text-blue-600 font-bold text-lg rounded-xl hover:bg-gray-100 shadow-2xl transition-all inline-flex items-center gap-3"
                    >
                        <Zap className="w-6 h-6 fill-current" />
                        Get Started for Free
                        <ArrowRight className="w-6 h-6" />
                    </motion.button>
                </motion.div>
            </section>

            {/* Footer */}
            <footer className="py-12 px-6 bg-white dark:bg-gray-900/80 border-t border-gray-200 dark:border-gray-800">
                <div className="max-w-6xl mx-auto">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-6">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl">
                                <Shield className="w-5 h-5 text-white fill-current" />
                            </div>
                            <span className="font-bold text-lg bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">Scout</span>
                        </div>
                        <p className="text-sm text-gray-500">
                            © 2025 Scout. Professional Security Scanning Platform.
                        </p>
                    </div>
                </div>
            </footer>

            <style>{`
                @keyframes gradient {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
                .animate-gradient {
                    background-size: 200% 200%;
                    animation: gradient 3s ease infinite;
                }
            `}</style>
        </div>
    );
};

export default Landing;
