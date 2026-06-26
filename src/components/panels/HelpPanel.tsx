"use client";

export function HelpPanel() {
  return (
    <div className="p-6" data-testid="help-panel">
      <h1 className="text-2xl font-bold mb-6">Help</h1>

      <div className="space-y-6">
        <div>
          <h2 className="text-lg font-semibold mb-3">Keyboard Shortcuts</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2">Shortcut</th>
                <th className="text-left py-2">Action</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b">
                <td className="py-2 font-mono">Ctrl + K</td>
                <td className="py-2">Open command palette</td>
              </tr>
              <tr className="border-b">
                <td className="py-2 font-mono">Ctrl + B</td>
                <td className="py-2">Toggle sidebar</td>
              </tr>
              <tr className="border-b">
                <td className="py-2 font-mono">Ctrl + Shift + M</td>
                <td className="py-2">Open memory drawer</td>
              </tr>
              <tr className="border-b">
                <td className="py-2 font-mono">Ctrl + ,</td>
                <td className="py-2">Open settings</td>
              </tr>
              <tr className="border-b">
                <td className="py-2 font-mono">Escape</td>
                <td className="py-2">Close drawer/modal</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3">Documentation</h2>
          <a
            href="https://github.com/AngusKingC/sovereign-ai"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800"
          >
            View full documentation on GitHub
          </a>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3">Getting Started</h2>
          <ul className="list-disc list-inside space-y-2 text-sm text-gray-700">
            <li>Navigate views using the sidebar</li>
            <li>Monitor tasks in the Tasks panel</li>
            <li>Check worker status in the Workers panel</li>
            <li>Respond to approval requests in the Approvals panel</li>
            <li>Track costs in the Costs panel</li>
            <li>Manage memory slots in the Memory drawer</li>
            <li>Configure settings in the Settings drawer</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
