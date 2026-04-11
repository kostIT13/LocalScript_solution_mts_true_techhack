import { authService } from './auth';
import type { UploadedDocument } from '../types';

const API_BASE = '/api/v1';

export class UploadApi {
  async uploadDocument(
    file: File,
    onProgress?: (progressEvent: ProgressEvent) => void
  ): Promise<void> {
    console.log('📤 uploadApi.uploadDocument:', file.name);
    
    const formData = new FormData();
    formData.append('file', file);

    const token = authService.getToken();
    console.log('🔑 Токен:', token ? `${token.substring(0, 30)}...` : 'null');

    const response = await fetch(`${API_BASE}/documents/upload`, {
      method: 'POST',
      headers: authService.getUploadHeaders(),
      body: formData,
    });

    console.log('📥 Response status:', response.status);

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      console.error('❌ Upload error:', error);
      
      if (response.status === 401) {
        console.error('🔒 401 Unauthorized - logging out');
        authService.logout();
        window.location.reload();
      }
      
      throw new Error(error.detail || `Upload failed: ${response.status}`);
    }

    const data = await response.json();
    console.log('✅ Upload success:', data);
    return data;
  }

  async getDocuments(): Promise<UploadedDocument[]> {
    console.log('📚 uploadApi.getDocuments()');
    
    const token = authService.getToken();
    console.log('🔑 Токен:', token ? `${token.substring(0, 30)}...` : 'null');
    
    const response = await fetch(`${API_BASE}/documents`, {
      headers: authService.getAuthHeaders(),
    });
    
    console.log('📥 Response status:', response.status);
    
    if (!response.ok) {
      if (response.status === 401) {
        console.error('🔒 401 Unauthorized - logging out');
        authService.logout();
        window.location.reload();
      }
      console.error('❌ Get documents error:', response.statusText);
      throw new Error('Failed to fetch documents');
    }
    
    const data = await response.json();
    console.log('✅ Get documents success:', data.length, 'documents');
    console.log('📄 Documents:', data);
    return data;
  }

  async deleteDocument(docId: string): Promise<void> {
    console.log('🗑️ uploadApi.deleteDocument:', docId);
    
    const response = await fetch(`${API_BASE}/documents/${docId}`, {
      method: 'DELETE',
      headers: authService.getAuthHeaders(),
    });
    
    console.log('📥 Response status:', response.status);
    
    if (!response.ok) {
      if (response.status === 401) {
        console.error('🔒 401 Unauthorized - logging out');
        authService.logout();
        window.location.reload();
      }
      console.error('❌ Delete document error:', response.statusText);
      throw new Error('Failed to delete document');
    }
    
    console.log('✅ Delete success');
  }
}

export const uploadApi = new UploadApi();