import { Outlet } from "react-router-dom";

import { Sidebar } from "@/components/layout/Sidebar";

export function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-[#f4f6f6]">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-[1600px] px-8 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
