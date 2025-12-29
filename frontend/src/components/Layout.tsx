import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

import { ThemeProvider } from '../context/ThemeContext';

const LayoutContent = () => {
    return (
        <div className="h-screen bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100 flex overflow-hidden transition-colors duration-300">
            <Sidebar />
            <main className="flex-1 ml-64 p-8 h-full overflow-y-auto">
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
