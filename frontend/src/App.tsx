import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ProtectedRoute } from "@/components/layout/ProtectedRoute";
import { AiInsightsPage } from "@/pages/AiInsightsPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { CarePlansPage } from "@/pages/CarePlansPage";
import { CareRecordsPage } from "@/pages/CareRecordsPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { LoginPage } from "@/pages/LoginPage";
import { MedicationsPage } from "@/pages/MedicationsPage";
import { ReportsPage } from "@/pages/ReportsPage";
import { ResidentDetailPage } from "@/pages/ResidentDetailPage";
import { ResidentsPage } from "@/pages/ResidentsPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { StaffPage } from "@/pages/StaffPage";
import {LoginPagekeyCloak} from "@/pages/LoginPageKeycloak.tsx";

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPagekeyCloak />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/residents" element={<ResidentsPage />} />
          <Route path="/residents/:id" element={<ResidentDetailPage />} />
          <Route path="/care-records" element={<CareRecordsPage />} />
          <Route path="/care-plans" element={<CarePlansPage />} />
          <Route path="/medications" element={<MedicationsPage />} />
          <Route path="/ai-insights" element={<AiInsightsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/calendar" element={<CalendarPage />} />
          <Route path="/staff" element={<StaffPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

export default App;
