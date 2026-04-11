// frontend/src/services/uploadApi.ts

import { authService } from './auth';
import type { UploadedDocument } from '../types';

const API_BASE = '/api/v1';

export class UploadApi {
  async uploadDocument(
    file: File,
    onProgress?: (progressEvent: ProgressEvent) => void
  ): Promise<void> {
    const formData = new FormData();
    formData.append('file', file);  // 🔹 Имя должно совпадать с бэкендом

    const response = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      headers: authService.getUploadHeaders(),  // 🔹 Без Content-Type!
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      
      // Если 401 — редирект на логин
      if (response.status === 401) {
        authService.logout();
        window.location.reload();
      }
      
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }

    return response.json();
  }

  async getDocuments(): Promise<UploadedDocument[]> {
    const response = await fetch(`${API_BASE}/documents`, {
      headers: authService.getAuthHeaders(),  // 🔹 Для JSON-запросов
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        authService.logout();
        window.location.reload();
      }
      throw new Error('Failed to fetch documents');
    }
    
    return response.json();
  }

  async deleteDocument(docId: string): Promise<void> {
    const response = await fetch(`${API_BASE}/documents/${docId}`, {
      method: 'DELETE',
      headers: authService.getAuthHeaders(),  // 🔹 Для JSON-запросов
    });
    
    if (!response.ok) {
      if (response.status === 401) {
        authService.logout();
        window.location.reload();
      }
      throw new Error('Failed to delete document');
    }
  }
}

export const uploadApi = new UploadApi();