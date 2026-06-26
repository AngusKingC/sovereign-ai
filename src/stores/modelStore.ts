import { create } from "zustand";

export interface ModelInfo {
  model_id: string;
  name: string;
  source: string;
  adapter_compatibility: string[];
  task_tags: string[];
  download_status: string;
  downloaded_quantisation: string | null;
  license: string;
  description: string;
}

interface ModelState {
  models: ModelInfo[];
  activeModelId: string | null;
  searchQuery: string;
  filterTag: string | null;
  filterAdapter: string | null;
  isLoading: boolean;
  error: string | null;
  setModels: (models: ModelInfo[]) => void;
  setActiveModel: (modelId: string) => void;
  setSearchQuery: (query: string) => void;
  setFilterTag: (tag: string | null) => void;
  setFilterAdapter: (adapter: string | null) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useModelStore = create<ModelState>((set) => ({
  models: [],
  activeModelId: null,
  searchQuery: "",
  filterTag: null,
  filterAdapter: null,
  isLoading: false,
  error: null,
  setModels: (models) => set({ models }),
  setActiveModel: (modelId) => set({ activeModelId: modelId }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setFilterTag: (tag) => set({ filterTag: tag }),
  setFilterAdapter: (adapter) => set({ filterAdapter: adapter }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));
