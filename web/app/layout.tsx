import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display", weight: ["500", "600", "700"] });

export const metadata: Metadata = {
  title: "Recall",
  description: "Ask your past. It answers with proof.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${display.variable} font-sans antialiased`}>
        <div className="aurora" aria-hidden />
        {children}
      </body>
    </html>
  );
}
