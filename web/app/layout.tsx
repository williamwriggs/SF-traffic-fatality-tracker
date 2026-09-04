import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SF Traffic Fatality Tracker",
  description:
    "A revision-aware tracker for San Francisco traffic fatalities, researched by William W. Riggs.",
  metadataBase: new URL("https://sf-traffic-fatality-tracker.vercel.app"),
  openGraph: {
    title: "SF Traffic Fatality Tracker",
    description: "Compare years, modes, locations, and revisions in official DataSF records.",
    type: "website",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#fbfaf7",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
