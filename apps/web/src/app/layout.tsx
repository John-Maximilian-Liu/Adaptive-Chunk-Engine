import type { Metadata } from "next";
import { Nav } from "@/components/Nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "Adaptive Chunk Engine",
  description: "Adaptive document chunking, retrieval evaluation, and governance",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto flex min-h-screen max-w-[1440px] gap-6 px-4 py-4 md:px-6">
          <Nav />
          <main className="min-w-0 flex-1 animate-rise [animation-delay:80ms]">{children}</main>
        </div>
      </body>
    </html>
  );
}
