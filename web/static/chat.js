// Terminal panel — xterm.js + WebSocket PTY
const Chat = {
  term: null,
  fit: null,
  ws: null,

  init() {
    const container = document.getElementById("panel-terminal");
    container.innerHTML = '<div id="terminal-container" style="height:calc(100vh - 120px);"></div>';

    // Wait for token before initializing terminal
    const checkToken = setInterval(() => {
      const token = localStorage.getItem('sovereign_token');
      if (token) {
        clearInterval(checkToken);
        requestAnimationFrame(() => this.setupTerminal());
      }
    }, 100);
  },

  setupTerminal() {
    const container = document.getElementById("terminal-container");
    if (!container || container.offsetWidth === 0) {
      requestAnimationFrame(() => this.setupTerminal());
      return;
    }

    this.term = new Terminal({
      cursorBlink: true,
      fontSize: 13,
      fontFamily: "monospace",
      theme: { background: "#0c0c0f", foreground: "#e0e0e0" },
    });
    this.fit = new FitAddon.FitAddon();
    this.term.loadAddon(this.fit);
    this.term.open(container);
    this.fit.fit();

    // Connect WebSocket with token in query string
    const token = localStorage.getItem('sovereign_token');
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/pty?token=${encodeURIComponent(token || '')}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.term.writeln("\r\n\x1b[32m● Connected to JArvis terminal\x1b[0m\r\n");
    };

    this.ws.onmessage = (event) => {
      this.term.write(event.data);
    };

    this.ws.onclose = () => {
      this.term.writeln("\r\n\x1b[31m● Disconnected\x1b[0m");
    };

    this.ws.onerror = () => {
      this.term.writeln("\r\n\x1b[31m● Connection error — is the backend running?\x1b[0m");
    };

    this.term.onData((data) => {
      if (this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(data);
      }
    });

    // Resize handling
    window.addEventListener("resize", () => {
      try { this.fit.fit(); } catch {}
    });
  },
};
