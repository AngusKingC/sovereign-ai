import "@testing-library/jest-dom";

// Mock EventSource for tests
global.EventSource = class EventSource {
  url: string;
  withCredentials: boolean;
  onopen: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;

  constructor(url: string, eventSourceInitDict?: EventSourceInit) {
    this.url = url;
    this.withCredentials = eventSourceInitDict?.withCredentials || false;
  }

  close() {
    // Mock implementation
  }

  CONNECTING = 0;
  OPEN = 1;
  CLOSED = 2;
  readyState = this.CONNECTING;
} as any;
