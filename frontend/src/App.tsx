import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AuthProvider } from "@/hooks/AuthProvider"
import { ProtectedRoute } from "@/components/layout/ProtectedRoute"
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
          <Route element={<ProtectedRoute />}>
            <Route path="/collections" element={<CollectionsPage />} />
            <Route path="/collections/:collectionId/upload" element={<UploadPage />} />
            <Route path="/connect" element={<ConnectPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/collections" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
