import { create } from "zustand";

interface MemorySlot {
  index: number;
  key: string;
  value: string;
  activation: number;
  lastWritten: number;
}

interface MemoryState {
  slots: Map<number, MemorySlot>;
  totalSlots: number;
  activeSlots: number;
  setActivation: (index: number, level: number) => void;
  getSlot: (index: number) => MemorySlot | undefined;
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  slots: new Map(),
  totalSlots: 512,
  activeSlots: 0,
  setActivation: (index, level) =>
    set((state) => {
      const slots = new Map(state.slots);
      const slot = slots.get(index);
      if (slot) {
        slots.set(index, { ...slot, activation: level });
      }
      const activeSlots = Array.from(slots.values()).filter((s) => s.activation > 0.1).length;
      return { slots, activeSlots };
    }),
  getSlot: (index) => get().slots.get(index),
}));
