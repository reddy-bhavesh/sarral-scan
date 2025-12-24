import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';
import { motion, useScroll, useTransform } from 'framer-motion';
import {
    Shield, Search, Activity, FileText, Zap, Sparkles,
    Target, ServerCog, Brain, CheckCircle, ArrowRight, 
    Star, Code2, Moon, Sun
} from 'lucide-react';
import { useState, useEffect } from 'react';

const Landing = () => {
    const navigate = useNavigate();
    const { user } = useAuth();
    const { theme, toggleTheme } = useTheme();
    const { scrollY } = useScroll();
    const [hoveredFeature, setHoveredFeature] = useState<number | null>(null);
    const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
    
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
            title: '20+ Security Tools',
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
                            Comprehensive penetration testing with <span className="font-bold text-blue-600 dark:text-blue-400">20+ integrated tools</span>, 
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
