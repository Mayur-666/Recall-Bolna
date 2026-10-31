import type { Metadata, Viewport } from "next";
import { MotionReady } from "@/components/motion";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recall — ask what was decided",
  description: "Recall reads your meeting transcripts and answers voice questions with the exact quote, who said it, and when.",
};

export const viewport: Viewport = {
  themeColor: "#0d0d0c",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased text-ink bg-paper min-h-screen">
        <MotionReady />
        {children}
      </body>
    </html>
  );
}
