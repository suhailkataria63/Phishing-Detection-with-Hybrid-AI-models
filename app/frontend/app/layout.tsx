import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Phish Detector Console",
  description: "Security-focused phishing triage console for URL, email, and joint detection workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
