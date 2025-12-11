import { useState, useEffect } from 'react';
import api from '../api/axios';
import { 
    Users, Shield, Trash2, Search, Activity, 
    HardDrive, AlertTriangle, CheckCircle, XCircle 
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { AnimatePresence, motion } from 'framer-motion';

interface User {
    id: number;
    email: string;
    fullName: string;
    organization: string;
    isAdmin: boolean;
    isActive: boolean;
    createdAt: string;
}

interface Scan {
    id: number;
    target: string;
    status: string;
    date: string;
    user: {
        email: string;
    };
}

interface Stats {
    total_users: number;
    total_scans: number;
    active_scans: number;
    total_admins: number;
}

const AdminDashboard = () => {
    const { user: currentUser } = useAuth();
    const [stats, setStats] = useState<Stats | null>(null);
    const [users, setUsers] = useState<User[]>([]);
    const [recentScans, setRecentScans] = useState<Scan[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [page, setPage] = useState(1);
    const [totalPages, setTotalPages] = useState(1);
    const [search, setSearch] = useState('');
    const [message, setMessage] = useState({ type: '', text: '' });

    useEffect(() => {
        fetchStats();
        fetchRecentScans();
    }, []);

    useEffect(() => {
        if (message.text) {
            const timer = setTimeout(() => {
                setMessage({ type: '', text: '' });
            }, 3000);
            return () => clearTimeout(timer);
        }
    }, [message]);

    useEffect(() => {
        fetchUsers();
    }, [page, search]);

    const fetchStats = async () => {
        try {
            const res = await api.get('/admin/stats');
            setStats(res.data);
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    };

    const fetchUsers = async () => {
        try {
            const res = await api.get(`/admin/users?page=${page}&limit=10&search=${search}`);
            setUsers(res.data.users);
            setTotalPages(Math.ceil(res.data.total / 10));
        } catch (error) {
            console.error('Error fetching users:', error);
        }
    };

    const fetchRecentScans = async () => {
        try {
            const res = await api.get('/admin/recent-scans');
            setRecentScans(res.data);
            setIsLoading(false);
        } catch (error) {
            console.error('Error fetching recent scans:', error);
            setIsLoading(false);
        }
    };

    const handlePromote = async (userId: number, currentStatus: boolean) => {
        if (userId === currentUser?.id) return;
        try {
            await api.patch(`/admin/users/${userId}`, { isAdmin: !currentStatus });
            fetchUsers();
            fetchStats();
            setMessage({ type: 'success', text: `User ${!currentStatus ? 'promoted' : 'demoted'} successfully` });
        } catch (error) {
            setMessage({ type: 'error', text: 'Failed to update user role' });
        }
    };

    const handleToggleActive = async (userId: number, currentStatus: boolean) => {
        if (userId === currentUser?.id) return;
        try {
            await api.patch(`/admin/users/${userId}`, { isActive: !currentStatus });
            fetchUsers();
            setMessage({ type: 'success', text: `User ${!currentStatus ? 'activated' : 'deactivated'} successfully` });
        } catch (error) {
            setMessage({ type: 'error', text: 'Failed to update user status' });
        }
    };

    const handleDelete = async (userId: number) => {
        if (userId === currentUser?.id) return;
        if (!window.confirm('Are you sure you want to permanently delete this user? This action cannot be undone.')) return;
        
        try {
            await api.delete(`/admin/users/${userId}`);
            fetchUsers();
            fetchStats();
            setMessage({ type: 'success', text: 'User deleted successfully' });
        } catch (error) {
            setMessage({ type: 'error', text: 'Failed to delete user' });
        }
    };

    if (isLoading) return <div className="p-6 text-center">Loading Admin Dashboard...</div>;

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-8 relative">
            <div className="flex flex-col gap-2">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <Shield className="w-8 h-8 text-purple-600" />
                    Admin Dashboard
                </h1>
                <p className="text-gray-500 dark:text-gray-400">System overview and user management</p>
            </div>

            {/* Notification Toast */}
            <div className="absolute top-2 right-6 z-50">
                <AnimatePresence>
                    {message.text && (
                        <motion.div 
                            initial={{ opacity: 0, y: -20, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.95, transition: { duration: 0.2 } }}
                            className={`p-4 rounded-lg shadow-lg flex items-center gap-2 border ${
                                message.type === 'success' 
                                    ? 'bg-green-50 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800' 
                                    : 'bg-red-50 text-red-700 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800'
                            }`}
                        >
                            {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> : <AlertTriangle className="w-5 h-5" />}
                            <span className="font-medium">{message.text}</span>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Users</p>
                            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{stats?.total_users}</h3>
                        </div>
                        <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                            <Users className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                        </div>
                    </div>
                </div>
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Scans</p>
                            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{stats?.total_scans}</h3>
                        </div>
                        <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                            <HardDrive className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                        </div>
                    </div>
                </div>
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Active Scans</p>
                            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{stats?.active_scans}</h3>
                        </div>
                        <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                            <Activity className="w-6 h-6 text-green-600 dark:text-green-400" />
                        </div>
                    </div>
                </div>
                <div className="bg-white dark:bg-gray-800 p-6 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm">
                    <div className="flex justify-between items-start">
                        <div>
                            <p className="text-sm font-medium text-gray-500 dark:text-gray-400">Admins</p>
                            <h3 className="text-2xl font-bold text-gray-900 dark:text-white mt-2">{stats?.total_admins}</h3>
                        </div>
                        <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
                            <Shield className="w-6 h-6 text-orange-600 dark:text-orange-400" />
                        </div>
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* User Management */}
                <div className="lg:col-span-2 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">User Management</h2>
                        <div className="relative">
                            <Search className="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
                            <input
                                type="text"
                                placeholder="Search users..."
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                className="pl-9 pr-4 py-2 text-sm bg-gray-50 dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg focus:ring-2 focus:ring-purple-500 dark:text-white"
                            />
                        </div>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm text-gray-500 dark:text-gray-400">
                            <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-700 dark:text-gray-300 uppercase font-medium">
                                <tr>
                                    <th className="px-6 py-3">User</th>
                                    <th className="px-6 py-3">Status</th>
                                    <th className="px-6 py-3">Role</th>
                                    <th className="px-6 py-3 text-right">Actions</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                                {users.map((u) => (
                                    <tr key={u.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                        <td className="px-6 py-4">
                                            <div className="font-medium text-gray-900 dark:text-white">{u.fullName || 'No Name'}</div>
                                            <div className="text-xs text-gray-500">{u.email}</div>
                                            <div className="text-xs text-gray-400">{u.organization}</div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                                u.isActive 
                                                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' 
                                                    : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                                            }`}>
                                                {u.isActive ? 'Active' : 'Inactive'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                                                u.isAdmin 
                                                    ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-400' 
                                                    : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400'
                                            }`}>
                                                {u.isAdmin ? <Shield className="w-3 h-3" /> : <Users className="w-3 h-3" />}
                                                {u.isAdmin ? 'Admin' : 'User'}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4 text-right space-x-2">
                                            <button
                                                onClick={() => handlePromote(u.id, u.isAdmin)}
                                                disabled={u.id === currentUser?.id}
                                                className={`p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 ${
                                                    u.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : 'text-blue-600 dark:text-blue-400'
                                                }`}
                                                title={u.isAdmin ? "Demote to User" : "Promote to Admin"}
                                            >
                                                <Shield className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => handleToggleActive(u.id, u.isActive)}
                                                disabled={u.id === currentUser?.id}
                                                className={`p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 ${
                                                    u.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : 'text-orange-600 dark:text-orange-400'
                                                }`}
                                                title={u.isActive ? "Deactivate User" : "Activate User"}
                                            >
                                                {u.isActive ? <XCircle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                                            </button>
                                            <button
                                                onClick={() => handleDelete(u.id)}
                                                disabled={u.id === currentUser?.id}
                                                className={`p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 ${
                                                    u.id === currentUser?.id ? 'opacity-50 cursor-not-allowed' : 'text-red-600 dark:text-red-400'
                                                }`}
                                                title="Permanently Delete"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                     {/* Pagination Controls */}
                     <div className="p-4 border-t border-gray-200 dark:border-gray-700 flex justify-between items-center">
                        <button
                            disabled={page === 1}
                            onClick={() => setPage(p => p - 1)}
                            className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded disabled:opacity-50"
                        >
                            Previous
                        </button>
                        <span className="text-sm text-gray-500 dark:text-gray-400">
                            Page {page} of {totalPages}
                        </span>
                        <button
                            disabled={page === totalPages}
                            onClick={() => setPage(p => p + 1)}
                            className="px-3 py-1 text-sm bg-gray-100 dark:bg-gray-700 rounded disabled:opacity-50"
                        >
                            Next
                        </button>
                    </div>
                </div>

                {/* Recent Scans */}
                <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm overflow-hidden h-fit">
                    <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                        <h2 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                            <Activity className="w-5 h-5 text-blue-500" />
                            Recent Global Scans
                        </h2>
                    </div>
                    <div className="divide-y divide-gray-200 dark:divide-gray-700">
                        {recentScans.map((scan) => (
                            <div key={scan.id} className="p-4 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                                <div className="flex justify-between items-start mb-1">
                                    <span className="font-medium text-gray-900 dark:text-white truncate max-w-[150px]" title={scan.target}>
                                        {scan.target}
                                    </span>
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                                        scan.status === 'Completed' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
                                        scan.status === 'Running' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' :
                                        'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                                    }`}>
                                        {scan.status}
                                    </span>
                                </div>
                                <div className="flex justify-between items-center text-xs text-gray-500 dark:text-gray-400">
                                    <span>{scan.user.email}</span>
                                    <span>{new Date(scan.date).toLocaleString()}</span>
                                </div>
                            </div>
                        ))}
                        {recentScans.length === 0 && (
                            <div className="p-8 text-center text-gray-500 dark:text-gray-400">
                                No recent scans found.
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AdminDashboard;
