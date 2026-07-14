import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

import { ThemeProvider } from '../context/ThemeContext';

const LayoutContent = () => {
    const [collapsed, setCollapsed] = useState(() => localStorage.getItem('sidebar_collapsed') === '1');
    const toggle = () => setCollapsed((c) => {
        const next = !c;
        localStorage.setItem('sidebar_collapsed', next ? '1' : '0');
        return next;
    });
    return (
        <div className="h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 flex overflow-hidden transition-colors duration-300">
            <Sidebar collapsed={collapsed} onToggle={toggle} />
            <main className={`flex-1 ${collapsed ? 'ml-20' : 'ml-64'} p-8 h-full overflow-y-auto transition-all duration-300`}>
                <Outlet />
            </main>
        </div>
    );
};

const Layout = () => {
    return (
        <ThemeProvider>
            <LayoutContent />
        </ThemeProvider>
    );
};

export default Layout;
