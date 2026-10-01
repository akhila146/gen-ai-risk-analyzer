import React from 'react';

const riskClassName = (riskLevel = '') => {
  const normalized = riskLevel.toLowerCase();
  if (normalized.includes('high')) return 'risk-high';
  if (normalized.includes('medium')) return 'risk-medium';
  return 'risk-low';
};

export default function DashboardPanel({ summary, applications = [] }) {
  if (!summary) return null;

  const summaryCards = [
    { label: 'Total Applications', value: summary.total_applications ?? 0 },
    { label: 'Low Risk', value: summary.low_risk ?? 0, className: 'risk-low' },
    { label: 'Medium Risk', value: summary.medium_risk ?? 0, className: 'risk-medium' },
    { label: 'High Risk', value: summary.high_risk ?? 0, className: 'risk-high' },
  ];

  return (
    <div className="dashboard-panel">
      <div className="dashboard-header">
        <h3>Portfolio Dashboard</h3>
        <span>Portfolio overview</span>
      </div>

      <div className="dashboard-stats-grid">
        {summaryCards.map((card) => (
          <div key={card.label} className={`dashboard-stat ${card.className || ''}`}>
            <div className="dashboard-stat-label">{card.label}</div>
            <div className="dashboard-stat-value">{card.value}</div>
          </div>
        ))}
      </div>

      <div className="recent-applications-card">
        <div className="recent-applications-header">Recent Applications</div>
        {applications.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Applicant</th>
                  <th>Risk</th>
                  <th>Credit Score</th>
                  <th>Salary</th>
                  <th>Loan</th>
                </tr>
              </thead>
              <tbody>
                {applications.map((item) => (
                  <tr key={item.application_id || item.applicant_name || item.created_at}>
                    <td>{item.applicant_name || 'N/A'}</td>
                    <td>
                      <span className={`risk-badge ${riskClassName(item.risk_level)}`}>
                        {item.risk_level || 'Unknown'}
                      </span>
                    </td>
                    <td>{item.credit_score ?? 'N/A'}</td>
                    <td>{item.monthly_salary ?? 'N/A'}</td>
                    <td>{item.requested_loan_amount ?? 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-state">No applications have been analyzed yet.</p>
        )}
      </div>
    </div>
  );
}
