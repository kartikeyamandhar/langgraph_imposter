import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque } from "next/font/google";
import "./globals.css";

// Display face for the secret word, verdicts, and scores only — at most
// once per screen. Everything else stays on the system-ui stack.
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
});

export const metadata: Metadata = {
  title: "Blindspot",
  description: "One of you doesn't know the word.",
};

export const viewport: Viewport = {
  themeColor: "#131A26",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={bricolage.variable}>
      <body className="font-sans antialiased min-h-dvh">{children}</body>
    </html>
  );
}
