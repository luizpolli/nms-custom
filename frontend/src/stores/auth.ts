import { create } from 'zustand';

interface AuthUser {
  name: string;
}

interface AuthStore {
  user: AuthUser | null;
  login: (user: AuthUser) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthStore>()((set) => ({
  user: { name: 'admin' },
  login: (user) => set({ user }),
  logout: () => set({ user: null }),
}));
