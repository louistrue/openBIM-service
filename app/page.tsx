"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { ProcessedIFC } from "@/app/types/ifc";

// Dynamically import the IFCViewer component to avoid SSR issues with WebGPU
const IFCViewer = dynamic(() => import("@/app/components/IFCViewer"), {
  ssr: false,
});

export default function Home() {
  const [ifcData, setIfcData] = useState<ProcessedIFC | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch("http://localhost:8000/api/process-ifc", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Error processing file: ${response.statusText}`);
      }

      const data = await response.json();
      setIfcData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-between p-24">
      <div className="z-10 max-w-5xl w-full items-center justify-between font-mono text-sm">
        <h1 className="text-4xl font-bold mb-8">IFC Viewer</h1>

        <div className="mb-8">
          <label className="block text-sm font-medium mb-2">
            Upload IFC File
          </label>
          <input
            type="file"
            accept=".ifc"
            onChange={handleFileUpload}
            className="block w-full text-sm text-slate-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-full file:border-0
              file:text-sm file:font-semibold
              file:bg-violet-50 file:text-violet-700
              hover:file:bg-violet-100"
          />
        </div>

        {loading && (
          <div className="text-center mb-8">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
            <p className="mt-2">Processing IFC file...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-lg mb-8">
            {error}
          </div>
        )}

        {ifcData && (
          <div className="w-full aspect-video bg-gray-100 rounded-lg overflow-hidden">
            <IFCViewer data={ifcData} />
          </div>
        )}
      </div>
    </main>
  );
}
