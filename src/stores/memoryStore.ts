import { create } from "zustand";

export interface MemorySlot {
  index: number;
  key: string;
  value: string;
  activation: number;
  lastWritten: number;
}

interface MemoryState {
  slots: MemorySlot[];
  searchQuery: string;
  sortColumn: keyof MemorySlot | null;
  sortDirection: "asc" | "desc";
  setSlots: (slots: MemorySlot[]) => void;
  setSearchQuery: (query: string) => void;
  setSort: (column: keyof MemorySlot | null, direction: "asc" | "desc") => void;
}

export const useMemoryStore = create<MemoryState>((set) => ({
  slots: [],
  searchQuery: "",
  sortColumn: null,
  sortDirection: "asc",
  setSlots: (slots) => set({ slots }),
  setSearchQuery: (searchQuery) => set({ searchQuery }),
  setSort: (sortColumn, sortDirection) => set({ sortColumn, sortDirection }),
}));
