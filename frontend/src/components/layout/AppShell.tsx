import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { ToastContainer } from '../ui/Toast';

export function AppShell() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-50 dark:bg-gray-950">
      {/* Mobile overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 sm:hidden"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Desktop sidebar */}
      <div className="hidden sm:flex">
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((v) => !v)} />
      </div>

      {/* Mobile sidebar (drawer) */}
      <div
        className={`fixed inset-y-0 left-0 z-50 sm:hidden transition-transform duration-200 ${
          mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <Sidebar collapsed={false} onToggle={() => setMobileSidebarOpen(false)} />
      </div>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar onMenuToggle={() => setMobileSidebarOpen((v) => !v)} />
        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          <Outlet />
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
