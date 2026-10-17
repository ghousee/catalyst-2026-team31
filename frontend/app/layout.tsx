import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CAIL Operations Assistant",
  description: "Evidence-backed system health, troubleshooting, knowledge, and operator training for HPE NonStop",
};

// Applies the saved theme before first paint (light by default for the clean workspace UI).
const themeScript = `try{var t=localStorage.getItem("theme");document.documentElement.dataset.theme=t==="dark"?"dark":"light"}catch(e){document.documentElement.dataset.theme="light"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
