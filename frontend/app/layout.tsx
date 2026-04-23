import type { Metadata } from "next";
import "./globals.css";
import ClientRoot from "@/components/ClientRoot";
import { AppProvider } from "@/context/walletContext";
import { MatchmakingProvider } from "@/context/matchmakingContext";
import { ToastProvider } from "@/components/ui/toast";
import { ThemeProvider } from "next-themes";

export const metadata: Metadata = {
  title: "XLMate",
  description: "XLMate — Chess on Stellar",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="antialiased font-rowdies bg-background text-foreground">
        <ThemeProvider attribute="class" defaultTheme="dark" enableSystem disableTransitionOnChange>
          <AppProvider>
            <MatchmakingProvider>
              <ToastProvider>
                <ClientRoot>{children}</ClientRoot>
              </ToastProvider>
            </MatchmakingProvider>
          </AppProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
