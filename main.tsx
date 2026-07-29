import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { PlannerWorkspace } from "@/components/planner-workspace";
import "@/styles/globals.css";

const root = document.getElementById("root");

if (!root) throw new Error("缺少前端挂载节点");

createRoot(root).render(
  <StrictMode>
    <PlannerWorkspace />
  </StrictMode>,
);
