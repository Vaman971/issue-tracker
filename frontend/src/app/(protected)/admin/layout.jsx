import RoleProtectedRoute from "@/components/RoleProtectedRoute/page";

export default function AdminLayout({children}) {
    return (
        <RoleProtectedRoute allowedRoles={["admin"]}>
            {children}
        </RoleProtectedRoute>
    )
}