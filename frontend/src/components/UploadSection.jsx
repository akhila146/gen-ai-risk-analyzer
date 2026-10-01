import React, { useRef } from 'react';
import { UploadCloud, X } from 'lucide-react';

export default function UploadSection({
  selectedFiles,
  onFileSelect,
  onClearFile,
  onAnalyze,
  loading,
}) {
  const fileInputRef = useRef(null);

  const validPdfFiles = (files) =>
    Array.from(files || []).filter(
      (file) => file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
    );

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const pdfFiles = validPdfFiles(e.dataTransfer.files);

    if (pdfFiles.length > 0) {
      onFileSelect(pdfFiles);
    } else {
      alert('Please upload valid PDF document(s) only.');
    }
  };

  const handleChange = (e) => {
    const pdfFiles = validPdfFiles(e.target.files);

    if (pdfFiles.length > 0) {
      onFileSelect(pdfFiles);
    } else {
      alert('Please upload valid PDF document(s) only.');
    }

    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="upload-card">
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleChange}
        accept="application/pdf,.pdf"
        multiple
        aria-label="Upload PDF files"
        style={{
          position: 'absolute',
          width: '1px',
          height: '1px',
          opacity: 0,
          pointerEvents: 'none',
          overflow: 'hidden',
        }}
      />
      <div
        className="drop-zone"
        onClick={() => fileInputRef.current && fileInputRef.current.click()}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <UploadCloud size={24} color="#1b5e20" style={{ marginBottom: 6 }} />
        <div className="drop-text">
          {selectedFiles && selectedFiles.length > 0
            ? 'Selected PDFs ready for analysis'
            : 'Upload applicant financial PDFs here'}
        </div>

        {selectedFiles && selectedFiles.length > 0 && (
          <div className="selected-files-list">
            {selectedFiles.map((file, index) => (
              <div key={`${file.name}-${index}`} className="selected-file-badge">
                <span>{file.name}</span>
              </div>
            ))}
            <button
              type="button"
              className="clear-file-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (onClearFile) onClearFile();
              }}
              aria-label="Remove selected files"
            >
              <X size={14} />
            </button>
          </div>
        )}
      </div>

      <div className="button-center-wrapper">
        <button
          className="analyze-btn"
          onClick={onAnalyze}
          disabled={!selectedFiles || selectedFiles.length === 0 || loading}
        >
          {loading ? 'Analyzing...' : selectedFiles && selectedFiles.length > 1 ? 'Analyze All' : 'Analyze'}
        </button>
      </div>
    </div>
  );
}