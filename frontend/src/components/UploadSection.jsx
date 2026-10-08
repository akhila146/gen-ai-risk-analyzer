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

  // Allow all types of files instead of restricting to PDF only
  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files || []);

    if (files.length > 0) {
      onFileSelect(files);
    } else {
      alert('Please upload valid document(s).');
    }
  };

  const handleChange = (e) => {
    const files = Array.from(e.target.files || []);

    if (files.length > 0) {
      onFileSelect(files);
    } else {
      alert('Please upload valid document(s).');
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
        multiple
        aria-label="Upload files"
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
            ? 'Selected files ready for analysis'
            : 'Upload applicant financial files here (PDF, Word, Text, etc.)'}
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