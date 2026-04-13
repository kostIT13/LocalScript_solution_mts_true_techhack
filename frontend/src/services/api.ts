import { authService } from './auth';
import type { GenerateRequest, StreamMessage, DoneMessage } from '../types';

const API_BASE = '/api/v1';

export class ApiClient {
  private abortController: AbortController | null = null;

  private getHeaders() {
    return authService.getAuthHeaders();
  }

  async generateLua(
    request: GenerateRequest,
    onToken: (token: string) => void,
    onComplete: (done: DoneMessage) => void,
    onError: (error: string) => void,
    useRag: boolean = false
  ): Promise<void> {
    this.abortController = new AbortController();

    const endpoint = useRag ? '/generate/lua_rag' : '/generate/lua';

    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: this.getHeaders(),  
        body: JSON.stringify(request),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        if (response.status === 401) {
          authService.logout();
          window.location.reload();
          throw new Error('Session expired');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error('No response body');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6).trim();
            
            console.log('📩 SSE received:', data);
            
            if (data === '[DONE]') continue;

            try {
              const message: StreamMessage = JSON.parse(data);
              
              if (message.type === 'token') {
                onToken(message.data);
              } else if (message.type === 'done') {
                console.log('✅ Done message:', message);
                onComplete(message);
              }
            } catch (e) {
              console.error('❌ Parse error:', e, 'Data:', data);
            }
          }
        }
      }
    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Generation aborted');
      } else {
        console.error('❌ API error:', error);
        onError(error instanceof Error ? error.message : 'Unknown error');
      }
    } finally {
      this.abortController = null;
    }
  }

  abort() {
    this.abortController?.abort();
  }
}

export const apiClient = new ApiClient();