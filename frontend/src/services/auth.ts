const API_BASE = '/api/v1';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  username?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  username?: string;
  is_active: boolean;
}

export class AuthService {
  private tokenKey = 'auth_token';
  private userKey = 'auth_user';

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  setToken(token: string): void {
    localStorage.setItem(this.tokenKey, token);
  }

  removeToken(): void {
    localStorage.removeItem(this.tokenKey);
    localStorage.removeItem(this.userKey);
  }

  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  getAuthHeaders(): Record<string, string> {
    const token = this.getToken();
    return {
      'Content-Type': 'application/json',
      'Authorization': token ? `Bearer ${token}` : '',
    };
  }

  getUploadHeaders(): Record<string, string> {
    const token = this.getToken();
    return {
      'Authorization': token ? `Bearer ${token}` : '',
    };
  }

  async login(data: LoginRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Login failed');
    }

    const tokenData: TokenResponse = await response.json();
    this.setToken(tokenData.access_token);
    
    try {
      const user = await this.getCurrentUser();
      localStorage.setItem(this.userKey, JSON.stringify(user));
    } catch (e) {
      console.warn('Failed to load user profile:', e);
    }

    return tokenData;
  }

  async register(data: RegisterRequest): Promise<TokenResponse> {
    const response = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Registration failed');
    }

    const tokenData: TokenResponse = await response.json();
    this.setToken(tokenData.access_token);

    return tokenData;
  }

  async getCurrentUser(): Promise<User> {
    const response = await fetch(`${API_BASE}/auth/me`, {
      headers: this.getAuthHeaders(),
    });

    if (!response.ok) {
      this.removeToken();
      throw new Error('Not authenticated');
    }

    return response.json();
  }

  logout(): void {
    this.removeToken();
    window.location.reload();
  }

  getCachedUser(): User | null {
    const userStr = localStorage.getItem(this.userKey);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }
}

export const authService = new AuthService();