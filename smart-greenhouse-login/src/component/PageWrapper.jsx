// src/components/PageWrapper.jsx
import React from 'react';
import { Link } from 'react-router-dom';
import '../style/Dashboard.css';

/**
 * PageWrapper is a layout component that provides a consistent sidebar
 * and main content area across the app.
 * It wraps any child content passed to it.
 */
export default function PageWrapper({ children }) {
  return (
    <div className="d-flex">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <h2 className="m-4">Smart GreenHouse</h2>
        <nav className="mt-4">
          <ul>
            <li><Link to="/dashboard">Dashboard</Link></li>
            <li><Link to="/history">History</Link></li>
            <li><Link to="/growth-gallery">Plant Growth</Link></li>
            <li><Link to="/settings">Settings</Link></li>
          </ul>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="dashboard-main p-4 flex-grow-1">
        {children}
      </main>
    </div>
  );
}