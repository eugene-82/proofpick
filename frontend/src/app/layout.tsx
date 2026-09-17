import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ProofPick",
  description: "공개 근거를 바탕으로 구매 판단을 돕는 ProofPick",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
