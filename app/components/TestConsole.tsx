"use client";

import { useState } from "react";

export default function TestConsole() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSplitByStorey = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(
        "http://localhost:8000/api/split-by-storey",
        {
          method: "POST",
          body: formData,
        }
      );

      if (!response.ok) {
        throw new Error(`Error: ${response.statusText}`);
      }

      // Trigger file download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "storeys.zip";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

      setResult("Success! Check your downloads folder.");
    } catch (error) {
      setResult(error instanceof Error ? error.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mt-8 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
      <h2 className="text-xl font-bold mb-4">Test Console</h2>

      {/* Split by Storey Test */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold mb-2">Split IFC by Storey</h3>
        <div className="flex items-center gap-4">
          <input
            type="file"
            accept=".ifc"
            onChange={handleSplitByStorey}
            disabled={loading}
            className="block w-full text-sm text-slate-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-full file:border-0
              file:text-sm file:font-semibold
              file:bg-violet-50 file:text-violet-700
              hover:file:bg-violet-100
              disabled:opacity-50 disabled:cursor-not-allowed"
          />
          {loading && (
            <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-900 dark:border-white"></div>
          )}
        </div>
        {result && (
          <div
            className={`mt-2 text-sm ${
              result.startsWith("Error") ? "text-red-500" : "text-green-500"
            }`}
          >
            {result}
          </div>
        )}
      </div>

      {/* Add more test functions here */}
    </div>
  );
}
