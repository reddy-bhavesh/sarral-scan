import React, { useState } from 'react';
import api from '../api/axios';
import { useNavigate, Link } from 'react-router-dom';
import { Shield, Mail, Lock, Eye, EyeOff, User, Building, Check } from 'lucide-react';

const Register = () => {
    const [formData, setFormData] = useState({
        full_name: '',
        email: '',
        organization: '',
        password: '',
        confirmPassword: ''
    });
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [agreeTerms, setAgreeTerms] = useState(false);
    const navigate = useNavigate();
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    const [passwordRules, setPasswordRules] = useState({
        length: false,
        uppercase: false,
        lowercase: false,
        number: false,
        special: false
    });

    const validatePassword = (pass: string) => {
        setPasswordRules({
            length: pass.length >= 8,
            uppercase: /[A-Z]/.test(pass),
            lowercase: /[a-z]/.test(pass),
            number: /\d/.test(pass),
            special: /[!@#$%^&*(),.?":{}|<>]/.test(pass)
        });
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value } = e.target;
        setFormData({ ...formData, [name]: value });
        
        if (name === 'password') {
            validatePassword(value);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (formData.password !== formData.confirmPassword) {
            setError("Passwords do not match");
            return;
        }

        if (!agreeTerms) {
            setError("You must agree to the Terms of Service");
            return;
        }

        setIsLoading(true);
        try {
            await api.post('/auth/register', {
                email: formData.email,
                password: formData.password,
                full_name: formData.full_name,
                organization: formData.organization
            });
            navigate('/login');
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Registration failed. Please try again.');
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-gray-50 dark:bg-[#0B1120] text-gray-900 dark:text-white relative overflow-hidden py-10 transition-colors duration-300">
            {/* Background Effects */}
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl pointer-events-none"></div>
            <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full blur-3xl pointer-events-none"></div>

            <div className="w-full max-w-md p-8 space-y-8 relative z-10">
                {/* Logo Section */}
                <div className="flex flex-col items-center justify-center mb-8">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-2.5 bg-blue-600 rounded-xl shadow-lg shadow-blue-500/20">
                            <Shield className="w-8 h-8 text-white fill-current" />
                        </div>
                        <span className="text-2xl font-bold tracking-tight">Scout</span>
                    </div>
                </div>

                {/* Register Card */}
                <div className="bg-white dark:bg-gray-900/50 backdrop-blur-xl border border-gray-200 dark:border-gray-800 rounded-2xl p-8 shadow-xl dark:shadow-2xl">
                    <div className="text-center mb-8">
                        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Create Account</h2>
                        <p className="text-gray-500 dark:text-gray-400 text-sm">Start securing your applications today</p>
                    </div>

                    {error && (
                        <div className="mb-6 p-3 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-lg text-red-600 dark:text-red-400 text-sm text-center">
                            {error}
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <div className="space-y-1.5">
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider ml-1">Full Name</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <User className="h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-500 transition-colors" />
                                </div>
                                <input
                                    type="text"
                                    name="full_name"
                                    value={formData.full_name}
                                    onChange={handleChange}
                                    className="block w-full pl-10 pr-3 py-2.5 bg-gray-50 dark:bg-gray-950/50 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                    placeholder="John Doe"
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider ml-1">Email Address</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Mail className="h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-500 transition-colors" />
                                </div>
                                <input
                                    type="email"
                                    name="email"
                                    value={formData.email}
                                    onChange={handleChange}
                                    className="block w-full pl-10 pr-3 py-2.5 bg-gray-50 dark:bg-gray-950/50 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                    placeholder="you@example.com"
                                    autoComplete="email"
                                    required
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider ml-1">Organization (Optional)</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Building className="h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-500 transition-colors" />
                                </div>
                                <input
                                    type="text"
                                    name="organization"
                                    value={formData.organization}
                                    onChange={handleChange}
                                    className="block w-full pl-10 pr-3 py-2.5 bg-gray-50 dark:bg-gray-950/50 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                    placeholder="Your Company"
                                />
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider ml-1">Password</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock className="h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-500 transition-colors" />
                                </div>
                                <input
                                    type={showPassword ? "text" : "password"}
                                    name="password"
                                    value={formData.password}
                                    onChange={handleChange}
                                    className="block w-full pl-10 pr-10 py-2.5 bg-gray-50 dark:bg-gray-950/50 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                    placeholder="Create a strong password"
                                    autoComplete="new-password"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors focus:outline-none"
                                >
                                    {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                                </button>
                            </div>
                            
                            {/* Password Strength Checklist */}
                            <div className="grid grid-cols-2 gap-2 mt-3 pl-1">
                                <div className={`flex items-center gap-2 text-xs ${passwordRules.length ? 'text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {passwordRules.length ? <Check className="w-3 h-3" /> : <div className="w-3 h-3 rounded-full border border-current" />}
                                    Min 8 chars
                                </div>
                                <div className={`flex items-center gap-2 text-xs ${passwordRules.uppercase ? 'text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {passwordRules.uppercase ? <Check className="w-3 h-3" /> : <div className="w-3 h-3 rounded-full border border-current" />}
                                    Uppercase
                                </div>
                                <div className={`flex items-center gap-2 text-xs ${passwordRules.lowercase ? 'text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {passwordRules.lowercase ? <Check className="w-3 h-3" /> : <div className="w-3 h-3 rounded-full border border-current" />}
                                    Lowercase
                                </div>
                                <div className={`flex items-center gap-2 text-xs ${passwordRules.number ? 'text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {passwordRules.number ? <Check className="w-3 h-3" /> : <div className="w-3 h-3 rounded-full border border-current" />}
                                    Number
                                </div>
                                <div className={`flex items-center gap-2 text-xs ${passwordRules.special ? 'text-green-600 dark:text-green-500' : 'text-gray-500 dark:text-gray-400'}`}>
                                    {passwordRules.special ? <Check className="w-3 h-3" /> : <div className="w-3 h-3 rounded-full border border-current" />}
                                    Special Char
                                </div>
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 uppercase tracking-wider ml-1">Confirm Password</label>
                            <div className="relative group">
                                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                                    <Lock className="h-5 w-5 text-gray-400 dark:text-gray-500 group-focus-within:text-blue-600 dark:group-focus-within:text-blue-500 transition-colors" />
                                </div>
                                <input
                                    type={showConfirmPassword ? "text" : "password"}
                                    name="confirmPassword"
                                    value={formData.confirmPassword}
                                    onChange={handleChange}
                                    className="block w-full pl-10 pr-10 py-2.5 bg-gray-50 dark:bg-gray-950/50 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-blue-500 transition-all"
                                    placeholder="Confirm your password"
                                    autoComplete="new-password"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                                    className="absolute inset-y-0 right-0 pr-3 flex items-center text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors focus:outline-none"
                                >
                                    {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                                </button>
                            </div>
                        </div>

                        <div className="flex items-center pt-1">
                            <label className="flex items-center space-x-2 cursor-pointer group">
                                <div className="relative flex items-center">
                                    <input
                                        type="checkbox"
                                        checked={agreeTerms}
                                        onChange={(e) => setAgreeTerms(e.target.checked)}
                                        className="peer h-4 w-4 rounded border-gray-300 dark:border-gray-600 bg-gray-100 dark:bg-gray-800 text-blue-600 focus:ring-blue-500/50 focus:ring-offset-0 transition-all"
                                    />
                                </div>
                                <span className="text-sm text-gray-600 dark:text-gray-400 group-hover:text-gray-800 dark:group-hover:text-gray-300 transition-colors">
                                    I agree to the <a href="#" className="text-blue-600 dark:text-blue-500 hover:text-blue-500 dark:hover:text-blue-400 font-medium">Terms of Service</a> and <a href="#" className="text-blue-600 dark:text-blue-500 hover:text-blue-500 dark:hover:text-blue-400 font-medium">Privacy Policy</a>
                                </span>
                            </label>
                        </div>

                        <button
                            type="submit"
                            disabled={isLoading || !Object.values(passwordRules).every(Boolean)}
                            className="w-full flex justify-center py-3 px-4 border border-transparent rounded-xl shadow-sm text-sm font-bold text-white bg-blue-600 hover:bg-blue-700 dark:hover:bg-blue-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-white dark:focus:ring-offset-gray-900 focus:ring-blue-500 transition-all disabled:opacity-70 disabled:cursor-not-allowed mt-6"
                        >
                            {isLoading ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                            ) : (
                                'Create Account'
                            )}
                        </button>
                    </form>

                    <div className="mt-8 text-center">
                        <p className="text-sm text-gray-600 dark:text-gray-500">
                            Already have an account?{' '}
                            <Link to="/login" className="font-medium text-blue-600 dark:text-blue-500 hover:text-blue-500 dark:hover:text-blue-400 transition-colors">
                                Sign In
                            </Link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Register;
