import { beforeEach, describe, expect, it, vi } from 'vitest';
import { clearToken, getToken, setToken } from './token-storage';

// vitest runs with environment 'node': no localStorage global, so the test
// stubs a minimal in-memory implementation instead of touching vite.config.
class MemoryStorage implements Storage {
  private store = new Map<string, string>();
  get length() {
    return this.store.size;
  }
  clear = () => this.store.clear();
  getItem = (key: string) => this.store.get(key) ?? null;
  key = (index: number) => Array.from(this.store.keys())[index] ?? null;
  removeItem = (key: string) => void this.store.delete(key);
  setItem = (key: string, value: string) => void this.store.set(key, value);
}

beforeEach(() => {
  vi.stubGlobal('localStorage', new MemoryStorage());
});

describe('token storage', () => {
  it('saves, reads and clears the token', () => {
    expect(getToken()).toBeNull();

    setToken('a-jwt');
    expect(getToken()).toBe('a-jwt');

    clearToken();
    expect(getToken()).toBeNull();
  });
});
