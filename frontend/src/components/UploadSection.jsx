import React, { useRef } from 'react';
import { UploadCloud, X } from 'lucide-react';

export default function UploadSection({ selectedFile, onFileSelect, onClearFile, onAnalyze, loading }) {
  const fileInputRef = useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        onFileSelect(file);
      } else {
        alert('Please upload a valid PDF document only.');
      }
    }
  };

  const handleChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      if (file.type === 'application/pdf' || file.name.endsWith('.pdf')) {
        onFileSelect(file);
      } else {
        alert('Please upload a valid PDF document only.');
      }
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
        accept="application/pdf"
        style={{ display: 'none' }}
      />
      <div
        className="drop-zone"
        onClick={() => fileInputRef.current && fileInputRef.current.click()}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        <UploadCloud size={24} color="#1b5e20" style={{ marginBottom: 6 }} />
        <div className="drop-text">Upload applicant financial PDF here</div>
        {selectedFile && (
          <div className="selected-file-badge">
            <span>Selected: {selectedFile.name}</span>
            <button
              type="button"
              className="clear-file-btn"
              onClick={(e) => {
                e.stopPropagation();
                if (onClearFile) onClearFile();
              }}
              aria-label="Remove selected file"
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
          disabled={!selectedFile || loading}
        >
          {loading ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>
    </div>
  );
}