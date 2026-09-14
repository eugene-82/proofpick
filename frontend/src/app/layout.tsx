import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProofPick",
  description: "Evidence-grounded purchase verification",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
