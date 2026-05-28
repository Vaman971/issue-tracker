import Providers from "./providers";
import "./globals.css"

export const metadata = {
  title: "Team Issue Tracker",
  description: "Intermediate full-stack issue tracker"
};

export default function RootLayout({children}) {
  return (
    <html lang="en">
      <body>
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  )
}