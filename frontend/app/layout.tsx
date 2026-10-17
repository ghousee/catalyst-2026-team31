import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NonStop Copilot",
  description: "Operator copilot for HPE NonStop, beside the CAIL 6530 terminal session",
};

// Applies the saved theme before first paint (dark by default).
const themeScript = `try{var t=localStorage.getItem("theme");document.documentElement.dataset.theme=t==="light"?"light":"dark"}catch(e){document.documentElement.dataset.theme="dark"}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
