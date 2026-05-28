import ProtectedRoute from "@/components/ProtectedRoute/page";
import Navbar from "@/components/Narbar/page";

export default function ProtectedLayout({children}) {
    return (
        <ProtectedRoute>
            <Navbar />
            {children}
        </ProtectedRoute>
    );
}