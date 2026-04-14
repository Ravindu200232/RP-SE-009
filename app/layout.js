import "./globals.css";
import Provider from "./provider";

export const metadata = {
    title: "AI Website Builder",
    description: "Build any app with AI - powered by Gemini",
};

export default function RootLayout({ children }) {
    return (
        <html lang="en" suppressHydrationWarning>
            <body>
                <Provider>
                    {children}
                </Provider>
            </body>
        </html>
    );
}
