import ProtectedRoute from "@/components/ProtectedRoute/page";
import Navbar from "@/components/Narbar/page";
import RagChatWidget from "@/components/RagChatWidget/page";

export default function ProtectedLayout({children}) {
    return (
        <ProtectedRoute>
            <Navbar />
            {children}
            {/* inside ProtectedRoute, so it exists on every signed-in page and
                on none of the public ones — no separate auth check needed */}
            <RagChatWidget />
        </ProtectedRoute>
    );
}