import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/AuthProvider"
import { AdminRoute } from "@/components/layout/AdminRoute"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
import { AdminPage } from "@/pages/admin/AdminPage"
import { InvitePage } from "@/pages/invite/InvitePage"
import { LoginPage } from "@/pages/login/LoginPage"
import { CollectionsPage } from "@/pages/collections/CollectionsPage"
import { UploadPage } from "@/pages/upload/UploadPage"
import { ConnectPage } from "@/pages/connect/ConnectPage"

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          {/* Public: the invitee has no account yet. */}
          <Route path="/invite/:token" element={<InvitePage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/collections" element={<CollectionsPage />} />
            <Route path="/collections/:collectionId/upload" element={<UploadPage />} />
            <Route path="/connect" element={<ConnectPage />} />
            <Route element={<AdminRoute />}>
              <Route path="/admin" element={<AdminPage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/collections" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
