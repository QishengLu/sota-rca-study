import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Overview', icon: '📊' },
  { path: '/cases', label: 'Case List', icon: '📋' },
  { path: '/comparison', label: 'Comparison', icon: '🔬' },
];

export function Sidebar() {
  return (
    <aside className="w-64 bg-white border-r border-slate-200 min-h-screen">
      <div className="p-6">
        <h1 className="text-xl font-bold text-slate-800">RCABench</h1>
        <p className="text-sm text-slate-500">Evaluation Dashboard</p>
      </div>
      <nav className="px-4">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors ${
                isActive
                  ? 'bg-primary-50 text-primary-700 font-medium'
                  : 'text-slate-600 hover:bg-slate-50'
              }`
            }
          >
            <span>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
