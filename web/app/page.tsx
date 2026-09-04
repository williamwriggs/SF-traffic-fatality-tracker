import Dashboard from "@/components/Dashboard";
import trackerData from "@/public/data/tracker.json";
import type { TrackerData } from "@/lib/types";

export default function Home() {
  return <Dashboard initialData={trackerData as TrackerData} />;
}
