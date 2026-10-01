import React, { useState, useEffect } from 'react';
import axios from 'axios';
import Header from './components/Header';
import HowItWorks from './components/HowItWorks';
import UploadSection from './components/UploadSection';
import ReportCards from './components/ReportCards';
import DashboardPanel from './components/DashboardPanel';
import ChatBot from './components/ChatBot';
import './App.css';

export default function App() {
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [analysisResults, setAnalysisResults] = useState([]);
  const [batchResults, setBatchResults] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [chatApplicationId, setChatApplicationId] = useState(null);
  const [selectedApplicationId, setSelectedApplicationId] = useState(null);
  const [warningMessage, setWarningMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const loadDashboard = async () => {
    try {
      const response = await axios.get('http://localhost:8000/api/dashboard');
      setDashboardData(response.data || null);
    } catch (err) {
      console.error('Dashboard load failed:', err);
    }
  };

  useEffect(() => {
    loadDashboard();
  }, []);

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
    setBatchResults([]);
    setChatApplicationId(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleClearSelectedFile = () => {
    setSelectedFiles([]);
    setReportData(null);
    setAnalysisResults([]);
    setBatchResults([]);
    setChatApplicationId(null);
    setSelectedApplicationId(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleSelectApplication = (applicationId) => {
    if (!applicationId) return;

    setChatApplicationId(applicationId);
    setSelectedApplicationId(applicationId);

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

    const endpoint = isSingleFile ? 'http://localhost:8000/api/analyze' : 'http://localhost:8000/api/analyze-bulk';

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

        setBatchResults([]);
      } else {
        const results = response.data.results || [];
        const validReports = results.filter((item) => item.data).map((item) => item.data);
        setBatchResults(results);
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
    const downloadUrl = `http://localhost:8000/api/download-report?application_id=${encodeURIComponent(applicationId)}`;
    window.open(downloadUrl, '_blank');
  };

  return (
    <div className="app-container">
      <Header />
      <main className="content-wrapper">
        <HowItWorks />

        <UploadSection
          selectedFiles={selectedFiles}
          onFileSelect={handleFileSelect}
          onClearFile={handleClearSelectedFile}
          onAnalyze={handleAnalyze}
          loading={loading}
        />

        {warningMessage && <div className="alert-box alert-warning">{warningMessage}</div>}
        {errorMessage && <div className="alert-box alert-error">{errorMessage}</div>}

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

        {dashboardData && (
          <DashboardPanel
            summary={dashboardData.summary}
            applications={dashboardData.recent_applications || []}
          />
        )}
      </main>

      <ChatBot
        applicationId={chatApplicationId}
        applications={dashboardData?.recent_applications || []}
        onSelectApplication={handleSelectApplication}
      />
    </div>
  );
}