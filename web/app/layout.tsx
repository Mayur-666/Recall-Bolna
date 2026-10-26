import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Recall — Voice-First Memory Companion",
  description: "Ask your past. It answers with proof.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased text-ink bg-paper min-h-screen">
        <div className="aurora" aria-hidden />
        {children}
      </body>
    </html>
  );
}
