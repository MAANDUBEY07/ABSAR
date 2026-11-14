/**
 * Root Layout Component
 * Provides global HTML shell, metadata, and navbar/footer layout wrapping.
 */

export const metadata = {
  title: "AVSAR – Opportunity Discovery & Eligibility Platform",
  description: "Bridging opportunities and beneficiaries",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
