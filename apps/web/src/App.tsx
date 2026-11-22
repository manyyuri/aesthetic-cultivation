import { NavLink, Outlet } from 'react-router-dom';

export function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand t-display">
          私人节目单
        </NavLink>
        <nav className="topnav">
          <NavLink to="/" end className={({ isActive }) => (isActive ? 'on' : '')}>
            今日
          </NavLink>
          <NavLink to="/issues" className={({ isActive }) => (isActive ? 'on' : '')}>
            合订本
          </NavLink>
          <NavLink to="/settings/subscribe" className={({ isActive }) => (isActive ? 'on' : '')}>
            订阅
          </NavLink>
        </nav>
      </header>
      <Outlet />
    </div>
  );
}
