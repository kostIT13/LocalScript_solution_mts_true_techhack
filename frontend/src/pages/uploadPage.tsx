import React, { useState, useEffect } from 'react';
import { uploadApi } from '../services/uploadApi';
import type { UploadedDocument } from '../types';
import '../index.css';

export default function UploadPage() {
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [documents, setDocuments] = useState<UploadedDocument[]>([]);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  useEffect(() => {
    console.log('📦 UploadPage mounted - loading documents...');
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      console.log('📚 Загрузка списка документов...');
      const docs = await uploadApi.getDocuments();
      console.log('✅ Загружено документов:', docs.length);
      console.log('📄 Документы:', docs);
      setDocuments(docs);
    } catch (error) {
      console.error('❌ Ошибка загрузки списка документов:', error);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const selectedFiles = Array.from(e.target.files);
      console.log('📁 Выбрано файлов:', selectedFiles.length);
      selectedFiles.forEach(f => {
        console.log(`  - ${f.name} (${f.size} байт, ${f.type})`);
      });
      setFiles(selectedFiles);
    }
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      console.warn('⚠️ Нет файлов для загрузки');
      return;
    }

    console.log('🚀 Начало загрузки файлов...');
    setUploading(true);
    setProgress(0);
    setMessage(null);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        
        console.log(`📤 Загрузка файла ${i + 1}/${files.length}:`, file.name);
        
        await uploadApi.uploadDocument(file, (progressEvent) => {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setProgress(percent);
          if (percent % 10 === 0) {  // Логируем каждые 10%
            console.log(`⏳ Прогресс загрузки ${file.name}: ${percent}%`);
          }
        });

        console.log('✅ Файл загружен:', file.name);
        
        setMessage({
          type: 'success',
          text: `✅ Файл "${file.name}" успешно загружен и индексируется!`
        });
      }

      console.log('🔄 Все файлы загружены, обновляем список...');
      setFiles([]);
      
      // 🔹 ВАЖНО: Обновить список после загрузки
      await loadDocuments();
      
      console.log('✅ Загрузка завершена, документов всего:', documents.length);
    } catch (error) {
      console.error('❌ Ошибка загрузки:', error);
      setMessage({
        type: 'error',
        text: `❌ Ошибка загрузки: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    } finally {
      setUploading(false);
      setProgress(0);
      console.log('🏁 Загрузка завершена (finally)');
    }
  };

  const handleDelete = async (docId: string) => {
    console.log('🗑️ Удаление документа:', docId);
    try {
      await uploadApi.deleteDocument(docId);
      console.log('✅ Документ удалён:', docId);
      setMessage({ type: 'success', text: '🗑️ Документ удалён' });
      await loadDocuments();
    } catch (error) {
      console.error('❌ Ошибка удаления:', error);
      setMessage({
        type: 'error',
        text: `❌ Ошибка удаления: ${error instanceof Error ? error.message : 'Unknown error'}`
      });
    }
  };

  const removeFile = (index: number) => {
    console.log('🗑️ Удаление файла из списка:', files[index].name);
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