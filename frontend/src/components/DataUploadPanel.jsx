import React, { useState } from 'react';
import axios from 'axios';

export default function DataUploadPanel() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError('');
      setMessage('');
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file first');
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post('/api/upload/dummy-data', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      setMessage(`✓ Data loaded successfully! 
        Users: ${response.data.records_loaded.users}
        Analysts: ${response.data.records_loaded.analysts}
        Instruments: ${response.data.records_loaded.instruments}
        Methods: ${response.data.records_loaded.methods}
        Jobs: ${response.data.records_loaded.jobs}`);
      setFile(null);
    } catch (err) {
      setError(`✗ Upload failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      border: '1px solid #ccc',
      borderRadius: '8px',
      padding: '16px',
      backgroundColor: '#f9f9f9',
      marginBottom: '16px'
    }}>
      <h3 style={{ marginTop: 0 }}>📁 Upload Dummy Data</h3>
      <p style={{ fontSize: '12px', color: '#666' }}>
        Load pre-configured test data (JSON format) to bypass database setup for quick demo.
      </p>
      
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
        <input
          type="file"
          accept=".json"
          onChange={handleFileSelect}
          disabled={loading}
          style={{ flex: 1 }}
        />
        <button
          onClick={handleUpload}
          disabled={loading || !file}
          style={{
            padding: '8px 16px',
            backgroundColor: loading || !file ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading || !file ? 'default' : 'pointer',
            fontWeight: 'bold'
          }}
        >
          {loading ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      {message && (
        <div style={{
          padding: '12px',
          backgroundColor: '#d4edda',
          color: '#155724',
          borderRadius: '4px',
          border: '1px solid #c3e6cb',
          fontSize: '12px',
          whiteSpace: 'pre-wrap'
        }}>
          {message}
        </div>
      )}

      {error && (
        <div style={{
          padding: '12px',
          backgroundColor: '#f8d7da',
          color: '#721c24',
          borderRadius: '4px',
          border: '1px solid #f5c6cb',
          fontSize: '12px',
          whiteSpace: 'pre-wrap'
        }}>
          {error}
        </div>
      )}

      <p style={{ fontSize: '11px', color: '#999', marginTop: '12px' }}>
        💡 <strong>Tip:</strong> Use <code>dummy_data.json</code> from the project root to load sample data.
      </p>
    </div>
  );
}
