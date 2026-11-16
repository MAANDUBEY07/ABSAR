import "./globals.css";
import "./theme.css";
import Script from "next/script";
import { AuthProvider } from "@/providers/AuthProvider";
import { ThemeProvider } from "@/providers/ThemeProvider";

export const metadata = {
  title: "AVSAR — Your next opportunity starts here",
  description: "Discover student opportunities, check eligibility, review trust indicators and stay ahead of application deadlines.",
  icons: { icon: "/avsar-logo-light.png" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="light">
      <head>
        <Script id="avsar-theme-init" strategy="beforeInteractive">{`(()=>{try{const t=localStorage.getItem("avsar-theme");if(t==="dark"||t==="light")document.documentElement.dataset.theme=t}catch{}})()`}</Script>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body><ThemeProvider><AuthProvider>{children}</AuthProvider></ThemeProvider></body>
    </html>
  );
}
