import React, { useState, useEffect } from 'react';
import { uploadApi }  from '../services/uploadApi';
import type { UploadedDocument } from '../types';
import '../index.css';

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const docs = await uploadApi.getDocuments();
      setDocuments(docs);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFiles(Array.from(e.target.files));
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) return;

    setUploading(true);
    setProgress(0);
    setMessage(null);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        await uploadApi.uploadDocument(file, (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percent);
        });

        setMessage({
          type: 'success',
          text: `✅ Файл "${file.name}" успешно загружен и индексируется!`
        });
      }

      setFiles([]);
      await loadDocuments();
    } catch (error) {
      setMessage({
        type: 'error',
        text: `❌ Ошибка загрузки: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const handleDelete = async (docId: string) => {
    try {
      await uploadApi.deleteDocument(docId);
      setMessage({ type: 'success', text: '🗑️ Документ удалён' });
      await loadDocuments();
    } catch (error) {
      setMessage({
        type: 'error',
        text: `❌ Ошибка удаления: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    }
  };

  const removeFile = (index: number) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  return (
    <div className="upload-page">
      <div className="upload-header">
        <h1>📚 Управление документами RAG</h1>
        <p>Загрузите Lua-документацию, примеры кода или руководства для использования в RAG</p>
      </div>

      <div className="upload-container">
        {/* 🔹 Зона загрузки */}
        <div className="upload-zone">
          <input
            type="file"
            id="file-input"
            multiple
            accept=".txt,.md,.lua,.py,.js,.ts"
            onChange={handleFileSelect}
            disabled={uploading}
          />
          <label htmlFor="file-input" className="upload-label">
            <div className="upload-icon">📁</div>
            <div className="upload-text">
              <strong>Нажмите для выбора файлов</strong>
              <span>или перетащите их сюда</span>
            </div>
            <div className="upload-hint">
              Поддерживаемые форматы: TXT, MD, LUA, PY, JS, TS
            </div>
          </label>
        </div>

        {/* 🔹 Список выбранных файлов */}
        {files.length > 0 && (
          <div className="selected-files">
            <h3>📋 Выбрано файлов: {files.length}</h3>
            <ul>
              {files.map((file, index) => (
                <li key={index} className="file-item">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">{(file.size / 1024).toFixed(1)} KB</span>
                  <button
                    onClick={() => removeFile(index)}
                    className="btn-remove"
                    disabled={uploading}
                  >
                    ✕
                  </button>
                </li>
              ))}
            </ul>
            <button
              onClick={handleUpload}
              className="btn-upload"
              disabled={uploading}
            >
              {uploading ? `⏳ Загрузка... ${progress}%` : `🚀 Загрузить ${files.length} файл(ов)`}
            </button>
            {uploading && (
              <div className="progress-bar">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        )}

        {/* 🔹 Сообщения */}
        {message && (
          <div className={`message ${message.type}`}>
            {message.text}
          </div>
        )}

        {/* 🔹 Список загруженных документов */}
        <div className="documents-list">
          <h3>📚 Загруженные документы ({documents.length})</h3>
          {documents.length === 0 ? (
            <p className="no-documents">Нет загруженных документов</p>
          ) : (
            <div className="documents-grid">
              {documents.map((doc) => (
                <div key={doc.id} className="document-card">
                  <div className="document-header">
                    <span className="document-icon">📄</span>
                    <h4>{doc.filename}</h4>
                  </div>
                  <div className="document-info">
                    <span>📊 Чанков: {doc.chunk_count || '...'}</span>
                    <span>📅 {new Date(doc.created_at).toLocaleDateString()}</span>
                    {doc.status && (
                      <span className={`status ${doc.status}`}>
                        {doc.status === 'completed' ? '✅' : doc.status === 'failed' ? '❌' : '⏳'} 
                        {doc.status}
                      </span>
                    )}
                  </div>
                  {doc.description && (
                    <p className="document-description">{doc.description}</p>
                  )}
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="btn-delete"
                  >
                    🗑️ Удалить
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}