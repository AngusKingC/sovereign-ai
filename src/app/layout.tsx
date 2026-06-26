import type { Metadata } from "next";
import { ShellClient } from "@/components/shell/ShellClient";
import "./globals.css";

export const metadata: Metadata = {
  title: "JArvis — Sovereign AI Operations",
  description: "Operational dashboard for Sovereign AI",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ShellClient>{children}</ShellClient>
      </body>
    </html>
  );
}
