import { create } from 'zustand';

type Health = {
  status: string;
  service: string;
  version: string;
  strategies_available: string[];
};

type AppState = {
  health: Health | null;
  setHealth: (h: Health | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  health: null,
  setHealth: (health) => set({ health }),
}));
