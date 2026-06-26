import { StatusBar } from "@/components/shell/StatusBar";
import { Sidebar } from "@/components/shell/Sidebar";
import { RightPanel } from "@/components/shell/RightPanel";
import { BottomBar } from "@/components/shell/BottomBar";
import "./globals.css";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="grid h-screen w-screen grid-rows-[auto_1fr_auto] grid-cols-[minmax(64px,200px)_1fr_400px]">
          <StatusBar className="col-span-3" />
          <Sidebar />
          <main className="flex items-center justify-center overflow-hidden bg-surface-base text-text-secondary">
            {children}
          </main>
          <RightPanel />
          <BottomBar className="col-span-3" />
        </div>
      </body>
    </html>
  );
}
