
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, PlusCircle, History, LogOut, Shield, Sun, Moon, User, ShieldAlert, Globe, Network, Target, ClipboardList, CalendarClock, Wrench, ShieldCheck, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

interface SidebarProps {
    collapsed?: boolean;
    onToggle?: () => void;
}

const Sidebar = ({ collapsed = false, onToggle }: SidebarProps) => {
    const { user, logout } = useAuth();
    const { theme, toggleTheme } = useTheme();

    const sections = [
        { title: null, items: [
            { path: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
        ]},
        { title: 'Scans', items: [
            { path: '/scan/new', icon: PlusCircle, label: 'New Scan' },
            { path: '/scan/history', icon: History, label: 'History' },
            { path: '/schedules', icon: CalendarClock, label: 'Schedules' },
        ]},
        { title: 'Exposure', items: [
            { path: '/attack-surface', icon: Network, label: 'Attack Surface' },
            { path: '/exposures', icon: Target, label: 'Exposures' },
            { path: '/remediation', icon: ClipboardList, label: 'Remediation' },
        ]},
        { title: 'Intel', items: [
            { path: '/breach-checker', icon: ShieldAlert, label: 'Breach Checker' },
            { path: '/webintel', icon: Globe, label: 'Web Intel' },
        ]},
        { title: 'Config', items: [
            { path: '/ai-tools', icon: Wrench, label: 'AI Tools' },
            { path: '/engagements', icon: ShieldCheck, label: 'Engagements' },
            ...(user?.isAdmin ? [{ path: '/admin', icon: Shield, label: 'Admin' }] : []),
        ]},
    ];

    const linkClass = ({ isActive }: { isActive: boolean }) =>
        `flex items-center ${collapsed ? 'justify-center px-0' : 'gap-3.5 px-3'} py-2.5 rounded-lg text-[15px] transition-colors ${
            isActive
                ? 'bg-blue-50 dark:bg-blue-600/10 text-blue-600 dark:text-blue-500'
                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-gray-200'
        }`;

    return (
        <div className={`${collapsed ? 'w-20' : 'w-64'} bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 flex flex-col h-screen fixed left-0 top-0 transition-all duration-300 z-30`}>
            <div className={`p-4 flex items-center ${collapsed ? 'justify-center' : 'justify-between'} border-b border-gray-200 dark:border-gray-800`}>
                {!collapsed && (
                    <div className="flex items-center gap-3 pl-2">
                        <div className="bg-blue-600 p-2 rounded-lg">
                            <Shield className="w-6 h-6 text-white" />
                        </div>
                        <span className="text-xl font-bold text-gray-900 dark:text-white">Scout</span>
                    </div>
                )}
                <button
                    onClick={onToggle}
                    title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    className="p-2 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 hover:text-gray-900 dark:hover:text-white transition-colors"
                >
                    {collapsed ? <PanelLeftOpen className="w-5 h-5" /> : <PanelLeftClose className="w-5 h-5" />}
                </button>
            </div>

            <nav className="flex-1 p-3 space-y-4 overflow-y-auto overflow-x-hidden custom-scrollbar">
                {sections.map((section, si) => (
                    <div key={si} className="space-y-1">
                        {section.title && !collapsed && (
                            <p className="px-3 pt-1 pb-0.5 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-600">
                                {section.title}
                            </p>
                        )}
                        {section.title && collapsed && si > 0 && (
                            <div className="mx-3 my-1 border-t border-gray-200 dark:border-gray-800" />
                        )}
                        {section.items.map((item) => (
                            <NavLink key={item.path} to={item.path} className={linkClass} title={collapsed ? item.label : undefined}>
                                <item.icon className="w-[21px] h-[21px] flex-shrink-0" />
                                {!collapsed && <span className="font-medium">{item.label}</span>}
                            </NavLink>
                        ))}
                    </div>
                ))}
            </nav>

            <div className="p-4 border-t border-gray-200 dark:border-gray-800 space-y-4">
                {/* Theme Toggle */}
                <button
                    onClick={toggleTheme}
                    title={collapsed ? (theme === 'dark' ? 'Dark Mode' : 'Light Mode') : undefined}
                    className={`flex items-center ${collapsed ? 'justify-center' : 'justify-between'} w-full px-4 py-2 bg-gray-100 dark:bg-gray-800 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors`}
                >
                    <span className={`flex items-center ${collapsed ? '' : 'gap-2'}`}>
                        {theme === 'dark' ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
                        {!collapsed && (theme === 'dark' ? 'Dark Mode' : 'Light Mode')}
                    </span>
                </button>

                <NavLink
                    to="/profile"
                    title={collapsed ? (user?.fullName || user?.email || 'Profile') : undefined}
                    className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3'} p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors group cursor-pointer`}
                >
                    <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-sm font-medium text-gray-600 dark:text-gray-300 group-hover:bg-blue-100 dark:group-hover:bg-blue-900/30 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors flex-shrink-0">
                        {user?.fullName ?
                            user.fullName.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2) :
                            user?.email?.slice(0, 2).toUpperCase() || 'US'}
                    </div>
                    {!collapsed && (
                        <div className="flex flex-col flex-1 min-w-0">
                            <span className="text-sm font-medium text-gray-900 dark:text-white truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                                {user?.fullName || user?.email?.split('@')[0] || 'User'}
                            </span>
                            {user?.organization && (
                                <span className="text-xs text-gray-500 truncate">{user.organization}</span>
                            )}
                        </div>
                    )}
                    {!collapsed && <User className="w-4 h-4 text-gray-400 group-hover:text-blue-500 transition-colors" />}
                </NavLink>

                <button
                    onClick={logout}
                    title={collapsed ? 'Logout' : undefined}
                    className={`flex items-center ${collapsed ? 'justify-center' : 'gap-3 px-3'} py-2 text-gray-500 dark:text-gray-400 hover:text-red-600 dark:hover:text-white hover:bg-red-50 dark:hover:bg-gray-800/50 rounded-lg transition-colors w-full`}
                >
                    <LogOut className="w-5 h-5 flex-shrink-0" />
                    {!collapsed && <span>Logout</span>}
                </button>
            </div>
        </div>
    );
};

export default Sidebar;
