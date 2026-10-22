import React, { useState } from 'react';
import { BarChart3, FileSearch, Files, LogOut, Moon, Sun, ShieldCheck } from 'lucide-react';

const navigation = [
  { id: 'upload', label: 'Analyze files', Icon: FileSearch },
  { id: 'reports', label: 'Reports', Icon: Files },
  { id: 'dashboard', label: 'Overview', Icon: BarChart3 },
];

export default function Header({ theme, user, onLogout, onToggleTheme }) {
  const [activeSection, setActiveSection] = useState('upload');
  const [profileOpen, setProfileOpen] = useState(false);

  const navigateTo = (id) => {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <aside className="app-sidebar" aria-label="Main navigation">
      <a className="brand-lockup" href="#upload" onClick={(event) => { event.preventDefault(); navigateTo('upload'); }}>
        <span className="brand-mark"><ShieldCheck size={21} aria-hidden="true" /></span>
        <span className="brand-name">Credit Risk Analyzer<span>CREDIT RISK ANALYSIS</span></span>
      </a>

      <div className="sidebar-label">WORKSPACE</div>
      <nav className="sidebar-navigation" aria-label="Workspace sections">
        {navigation.map(({ id, label, Icon }) => (
          <button
            key={id}
            type="button"
            className={`sidebar-link${activeSection === id ? ' sidebar-link-active' : ''}`}
            aria-current={activeSection === id ? 'location' : undefined}
            onClick={() => navigateTo(id)}
          >
            <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-spacer" />
      <div className="sidebar-label preferences-label">PREFERENCES</div>
      <button className="theme-control" type="button" onClick={onToggleTheme} aria-label="Dark theme" aria-pressed={theme === 'dark'}>
        <span className="theme-icon">{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</span>
        <span>Dark theme</span>
        <span className={`theme-switch${theme === 'dark' ? ' theme-switch-on' : ''}`} aria-hidden="true"><span /></span>
      </button>

      <div className="sidebar-profile">
        <div className="profile-avatar" aria-hidden="true">{user?.full_name?.charAt(0)?.toUpperCase() || 'U'}</div>
        <button
          className="profile-trigger"
          type="button"
          aria-haspopup="menu"
          aria-expanded={profileOpen}
          onClick={() => setProfileOpen((open) => !open)}
        >
          <span className="profile-copy">
            <strong>{user?.full_name || 'User'}</strong>
            <span>{user?.email || 'Risk workspace'}</span>
          </span>
        </button>
        {profileOpen && (
          <div className="profile-menu" role="menu" aria-label="Profile options">
            <button
              className="logout-button"
              type="button"
              role="menuitem"
              onClick={onLogout}
            >
              <LogOut size={17} aria-hidden="true" />
              <span>Log out</span>
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}