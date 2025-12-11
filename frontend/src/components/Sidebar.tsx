
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, History, LogOut, Shield, Sun, Moon, User } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const Sidebar = () => {
    const { user, logout } = useAuth();
    const { theme, toggleTheme } = useTheme();

    const navItems = [
        { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
        { path: '/scan/new', icon: PlusCircle, label: 'New Scan' },
        { path: '/scan/history', icon: History, label: 'Scan History' },
    ];

    return (
        <div className="w-64 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col h-screen fixed left-0 top-0 transition-colors duration-300">
            <div className="p-6 flex items-center gap-3 border-b border-gray-200 dark:border-gray-800">
                <div className="bg-blue-600 p-2 rounded-lg">
                    <Shield className="w-6 h-6 text-white" />
                </div>
                <span className="text-xl font-bold text-gray-900 dark:text-white">Sarral Scan</span>
            </div>

            <nav className="flex-1 p-4 space-y-2">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) =>
                            `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                                isActive
                                    ? 'bg-blue-50 dark:bg-blue-600/10 text-blue-600 dark:text-blue-500 border-r-2 border-blue-600 dark:border-blue-500'
                                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200'
                            }`
                        }
                    >
                        <item.icon className="w-5 h-5" />
                        <span className="font-medium">{item.label}</span>
                    </NavLink>
                ))}
                
                {user?.isAdmin && (
                    <NavLink
                        to="/admin"
                        className={({ isActive }) =>
                            `flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                                isActive
                                    ? 'bg-blue-50 dark:bg-blue-600/10 text-blue-600 dark:text-blue-500 border-r-2 border-blue-600 dark:border-blue-500'
                                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200'
                            }`
                        }
                    >
                        <Shield className="w-5 h-5" />
                        <span className="font-medium">Admin</span>
                    </NavLink>
                )}
            </nav>

            <div className="p-4 border-t border-gray-200 dark:border-gray-800 space-y-4">
                {/* Theme Toggle */}
                <button
                    onClick={toggleTheme}
                    className="flex items-center justify-between w-full px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                    <span className="flex items-center gap-2">
                        {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                        {theme === 'dark' ? 'Dark Mode' : 'Light Mode'}
                    </span>
                </button>

                <NavLink 
                    to="/profile"
                    className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group cursor-pointer"
                >
                    <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-sm font-medium text-gray-600 dark:text-gray-300 group-hover:bg-blue-100 dark:group-hover:bg-blue-900/30 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                        {user?.fullName ? 
                            user.fullName.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) : 
                            user?.email?.slice(0, 2).toUpperCase() || 'US'}
                    </div>
                    <div className="flex flex-col flex-1 min-w-0">
                        <span className="text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                            {user?.fullName || user?.email?.split('@')[0] || 'User'}
                        </span>
                        {user?.organization && (
                            <span className="text-xs text-gray-500 truncate">{user.organization}</span>
                        )}
                    </div>
                    <User className="w-4 h-4 text-gray-400 group-hover:text-blue-500 transition-colors" />
                </NavLink>

                <button
                    onClick={logout}
                    className="flex items-center gap-3 px-3 py-2 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-white hover:bg-red-50 dark:hover:bg-gray-800/50 rounded-lg transition-colors w-full"
                >
                    <LogOut className="w-5 h-5" />
                    <span>Logout</span>
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
