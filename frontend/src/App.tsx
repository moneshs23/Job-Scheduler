import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProjectProvider } from "./context/ProjectContext";
import { ToastProvider } from "./context/ToastContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Layout } from "./components/Layout";
import { LoginPage } from "./pages/Login";
import { RegisterPage } from "./pages/Register";
import { DashboardPage } from "./pages/Dashboard";
import { QueuesPage } from "./pages/Queues";
import { JobsPage } from "./pages/Jobs";
import { JobDetailPage } from "./pages/JobDetail";
import { WorkersPage } from "./pages/Workers";
import { DeadLetterQueuePage } from "./pages/DeadLetterQueue";
import { ApiKeysPage } from "./pages/ApiKeys";
import { AuditLogPage } from "./pages/AuditLog";

function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <ProjectProvider>
                  <Routes>
                    <Route element={<Layout />}>
                      <Route index element={<DashboardPage />} />
                      <Route path="queues" element={<QueuesPage />} />
                      <Route path="jobs" element={<JobsPage />} />
                      <Route path="jobs/:jobId" element={<JobDetailPage />} />
                      <Route path="workers" element={<WorkersPage />} />
                      <Route path="dead-letter" element={<DeadLetterQueuePage />} />
                      <Route path="api-keys" element={<ApiKeysPage />} />
                      <Route path="audit-log" element={<AuditLogPage />} />
                      <Route path="*" element={<Navigate to="/" replace />} />
                    </Route>
                  </Routes>
                </ProjectProvider>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </ToastProvider>
  );
}

export default App;
