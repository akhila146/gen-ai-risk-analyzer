import React from 'react';
import { Download } from 'lucide-react';

export default function ReportCards({ reportData, onDownload }) {
  if (!reportData) return null;

  const riskLevel = (reportData.risk_level || 'Unknown').toUpperCase();

  let themeClass = '';
  if (riskLevel.includes('LOW')) themeClass = 'theme-low';
  else if (riskLevel.includes('MEDIUM')) themeClass = 'theme-medium';
  else if (riskLevel.includes('HIGH')) themeClass = 'theme-high';

  return (
    <div className="report-section">
      <div className="report-heading">Analyzed Report</div>

      <div className="cards-grid">
        {/* Card 1: Risk Level */}
        <div className={`metric-card ${themeClass}`}>
          <div>
            <div className="card-title">Risk Level</div>
            <div className="card-value">{reportData.risk_level || 'N/A'}</div>
          </div>
          <div className="card-subtext">ID: {reportData.application_id || 'N/A'}</div>
        </div>

        {/* Card 2: Credit Score */}
        <div className="metric-card">
          <div>
            <div className="card-title">Credit Score</div>
            <div className="card-value">{reportData.credit_score || 'N/A'}</div>
          </div>
          <div className="card-subtext">{reportData.applicant_name || 'N/A'}</div>
        </div>

        {/* Card 3: Key Factors */}
        <div className="metric-card">
          <div className="card-title">Key Factors</div>
          <ul className="factors-list">
            {Array.isArray(reportData.key_factors) && reportData.key_factors.length > 0 ? (
              reportData.key_factors.map((factor, index) => (
                <li key={index}>{factor}</li>
              ))
            ) : (
              <li>{reportData.key_factors || 'No factors available'}</li>
            )}
          </ul>
          <div></div>
        </div>

        {/* Card 4: Recommendation */}
        <div className={`metric-card ${themeClass}`}>
          <div>
            <div className="card-title">Recommendation</div>
            <div className="card-value" style={{ fontSize: '0.95rem' }}>
              {reportData.recommendation || 'Under Review'}
            </div>
          </div>
          <div></div>
        </div>
      </div>

      <div className="download-action-row">
        <button className="download-btn" onClick={onDownload}>
          <Download size={15} /> Download Report
        </button>
      </div>
    </div>
  );
}