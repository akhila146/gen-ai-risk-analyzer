import React, { useState } from 'react';
import axios from 'axios';
import Header from './components/Header';
import HowItWorks from './components/HowItWorks';
import UploadSection from './components/UploadSection';
import ReportCards from './components/ReportCards';
import ChatBot from './components/ChatBot';
import './App.css';

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [warningMessage, setWarningMessage] = useState('');
  const [errorMessage, setErrorMessage] = useState('');

  const handleFileSelect = (file) => {
    setSelectedFile(file);
    setReportData(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleClearSelectedFile = () => {
    setSelectedFile(null);
    setReportData(null);
    setWarningMessage('');
    setErrorMessage('');
  };

  const handleAnalyze = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setWarningMessage('');
    setErrorMessage('');

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await axios.post('http://localhost:8000/api/analyze', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });

      const { status, data, message } = response.data;

      if (status === 'DATA_NOT_FOUND') {
        setErrorMessage(message || 'Data not found in the uploaded PDF.');
        setReportData(null);
      } else if (status === 'MISSING_FIELDS') {
        setWarningMessage(
          `Missing Critical Fields: ${data.missing_critical_fields?.join(', ') || 'Certain values missing'}. Risk cannot be fully evaluated.`
        );
        setReportData(data);
      } else {
        setReportData(data);
      }
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || 'Analysis failed. Make sure backend is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadReport = () => {
    const applicationId = reportData?.application_id || reportData?.applicant_id;
    if (!applicationId) return;
    const downloadUrl = `http://localhost:8000/api/download-report?application_id=${encodeURIComponent(
      applicationId
    )}`;
    window.open(downloadUrl, '_blank');
  };

  return (
    <div className="app-container">
      <Header />
      <main className="content-wrapper">
        <HowItWorks />

        <UploadSection
          selectedFile={selectedFile}
          onFileSelect={handleFileSelect}
          onClearFile={handleClearSelectedFile}
          onAnalyze={handleAnalyze}
          loading={loading}
        />

        {warningMessage && <div className="alert-box alert-warning">{warningMessage}</div>}
        {errorMessage && <div className="alert-box alert-error">{errorMessage}</div>}

        <ReportCards reportData={reportData} onDownload={handleDownloadReport} />
      </main>

      <ChatBot applicationId={reportData?.application_id || reportData?.applicant_id} />
    </div>
  );
}