import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { API_BASE_URL } from './api';
import Header from './components/Header';
import AuthPage from './components/AuthPage';
import HowItWorks from './components/HowItWorks';
import UploadSection from './components/UploadSection';
import ReportCards from './components/ReportCards';
import DashboardPanel from './components/DashboardPanel';
import ChatBot from './components/ChatBot';
import './App.css';

function Dashboard({ user, onLogout }) {
  const [theme, setTheme] = useState(() => window.localStorage.getItem('risk-analyzer-theme') || 'light');
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [analysisResults, setAnalysisResults] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [chatApplicationId, setChatApplicationId] = useState(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [warningMessage, setWarningMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const loadDashboard = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/dashboard`);
      setDashboardData(response.data || null);
    } catch (err) {
      console.error('Dashboard load failed:', err);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

  useEffect(() => {
    window.localStorage.setItem('risk-analyzer-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (analysisResults.length > 0) {
      const firstResult = analysisResults[0];
      const appId = firstResult?.application_id || firstResult?.applicant_id;
      if (appId) setChatApplicationId(appId);
      return;
    }

    if (reportData) {
      const appId = reportData.application_id || reportData.applicant_id;
      if (appId) setChatApplicationId(appId);
    }
  }, [analysisResults, reportData]);

  const handleFileSelect = (files) => {
    const nextFiles = Array.isArray(files) ? files : [files];
    setSelectedFiles(nextFiles);
    setReportData(null);
    setAnalysisResults([]);
    setChatApplicationId(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleClearSelectedFile = () => {
    setSelectedFiles([]);
    setReportData(null);
    setAnalysisResults([]);
    setChatApplicationId(null);
    setSelectedApplicationId(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleSelectApplication = (applicationId) => {
    setChatApplicationId(applicationId || null);
    setSelectedApplicationId(applicationId || null);

    const matchingAnalysis = analysisResults.find(
      (result) => (result.application_id || result.applicant_id) === applicationId
    );

    if (matchingAnalysis) {
      setReportData(matchingAnalysis);
    }
  };

  const handleAnalyze = async () => {
    if (!selectedFiles || selectedFiles.length === 0) return;

    setLoading(true);
    setWarningMessage('');
    setErrorMessage('');

    const formData = new FormData();
    const isSingleFile = selectedFiles.length === 1;

    if (isSingleFile) {
      formData.append('file', selectedFiles[0]);
    } else {
      selectedFiles.forEach((file) => {
        formData.append('files', file);
      });
    }

    const endpoint = isSingleFile ? `${API_BASE_URL}/api/analyze` : `${API_BASE_URL}/api/analyze-bulk`;

    try {
      const response = await axios.post(endpoint, formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      if (isSingleFile) {
        const { status, data, message } = response.data;

        if (status === 'DATA_NOT_FOUND') {
          setErrorMessage(message || 'Data not found in the uploaded PDF.');
          setReportData(null);
          setAnalysisResults([]);
        } else if (status === 'MISSING_FIELDS') {
          setWarningMessage(
            `Missing Critical Fields: ${data.missing_critical_fields?.join(', ') || 'Certain values missing'}. Risk cannot be fully evaluated.`
          );
          setReportData(data);
          setAnalysisResults([data]);
        } else {
          setReportData(data);
          setAnalysisResults([data]);
        }
      } else {
        const results = response.data.results || [];
        const validReports = results.filter((item) => item.data).map((item) => item.data);
        setAnalysisResults(validReports);
        setReportData(validReports[0] || null);

        if (results.some((item) => item.status === 'INVALID_FILE')) {
          setWarningMessage('Some uploaded files were skipped because they were not valid PDFs.');
        }
      }

      await loadDashboard();
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || 'Analysis failed. Make sure backend is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = (report = reportData) => {
    const applicationId = report?.application_id || report?.applicant_id;
    if (!applicationId) return;
    const downloadUrl = `${API_BASE_URL}/api/download-report?application_id=${encodeURIComponent(applicationId)}`;
    window.open(downloadUrl, '_blank');
  };

  return (
    <div className="app-container" data-theme={theme}>
      <Header
        theme={theme}
        user={user}
        onLogout={onLogout}
        onToggleTheme={() => setTheme((current) => current === 'light' ? 'dark' : 'light')}
      />
      <main className="content-wrapper">
        <h1 className="visually-hidden">Credit risk analysis</h1>
        <section id="upload" className="workspace-section" aria-labelledby="upload-heading">
          <h2 id="upload-heading" className="visually-hidden">Analyze files</h2>
          <HowItWorks />

          <UploadSection
            selectedFiles={selectedFiles}
            onFileSelect={handleFileSelect}
            onClearFile={handleClearSelectedFile}
            onAnalyze={handleAnalyze}
            loading={loading}
          />
        </section>

        {warningMessage && <div className="alert-box alert-warning">{warningMessage}</div>}
        {errorMessage && <div className="alert-box alert-error">{errorMessage}</div>}

        <section id="reports" className="workspace-section reports-section" aria-labelledby="results-heading">
          <div className="section-heading">
            <h2 id="results-heading">Application results</h2>
            <span>{analysisResults.length} analyzed in this session</span>
          </div>
          {analysisResults.length > 0 ? (
            analysisResults.map((result, index) => (
              <ReportCards
                key={`${result.application_id || result.applicant_id || 'report'}-${index}`}
                reportData={result}
                onDownload={() => handleDownloadReport(result)}
                isSelected={(result.application_id || result.applicant_id) === selectedApplicationId}
              />
            ))
          ) : (
            <ReportCards
              reportData={reportData}
              onDownload={handleDownloadReport}
              isSelected={Boolean(selectedApplicationId)}
            />
          )}
        </section>

        <section id="dashboard" className="dashboard-section" aria-labelledby="overview-heading">
          <h2 id="overview-heading" className="visually-hidden">Overview</h2>
          {dashboardData && (
            <DashboardPanel
              summary={dashboardData.summary}
              applications={dashboardData.recent_applications || []}
            />
          )}
        </section>
      </main>

      <ChatBot
        applicationId={chatApplicationId}
        applications={dashboardData?.recent_applications || []}
        onSelectApplication={handleSelectApplication}
      />
    </div>
  );
}

/**
 * Restore the server-side session and route unauthenticated visitors to login.
 */
export default function App() {
  const [path, setPath] = useState(window.location.pathname);
  const [search, setSearch] = useState(window.location.search);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [logoutError, setLogoutError] = useState('');

  const navigate = (destination) => {
    window.history.pushState({}, '', destination);
    setPath(window.location.pathname);
    setSearch(window.location.search);
  };

  useEffect(() => {
    const handlePopState = () => {
      setPath(window.location.pathname);
      setSearch(window.location.search);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  useEffect(() => {
    axios.get(`${API_BASE_URL}/api/auth/me`)
      .then((response) => setUser(response.data.user))
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  useEffect(() => {
    if (authLoading) return;
    const publicRoutes = ['/login', '/signup'];
    if (!user && !publicRoutes.includes(path)) navigate('/login');
    if (user && publicRoutes.includes(path)) navigate('/');
  }, [authLoading, path, user]);

  const handleAuthenticated = (authenticatedUser) => {
    setUser(authenticatedUser);
    setLogoutError('');
    navigate('/');
  };

  const handleLogout = async () => {
    setLogoutError('');
    try {
      await axios.post(`${API_BASE_URL}/api/auth/logout`);
      setUser(null);
      navigate('/login');
    } catch {
      setLogoutError('Unable to log out right now. Please try again.');
    }
  };

  if (authLoading) {
    return <main className="auth-loading" role="status">Checking your session…</main>;
  }

  if (user && !['/login', '/signup'].includes(path)) {
    return (
      <>
        {logoutError && <div className="auth-error auth-global-error" role="alert">{logoutError}</div>}
        <Dashboard user={user} onLogout={handleLogout} />
      </>
    );
  }

  const publicPath = ['/login', '/signup'].includes(path)
    ? path.slice(1)
    : 'login';
  return (
    <AuthPage
      page={publicPath}
      search={search}
      onNavigate={navigate}
      onAuthenticated={handleAuthenticated}
    />
  );
}