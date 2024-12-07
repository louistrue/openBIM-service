"use client";

import { useEffect, useState } from "react";
import { IFCElement } from "./types/elements";

export default function Home() {
  const [elements, setElements] = useState<IFCElement[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number>(0);
  const [processStats, setProcessStats] = useState<{
    processed: number;
    total: number;
  } | null>(null);
  const [uploadPhase, setUploadPhase] = useState<
    "idle" | "uploading" | "processing"
  >("idle");

  const handleFileUpload = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setLoading(true);
    setError(null);
    setProgress(0);
    setProcessStats(null);
    setElements([]);
    setUploadPhase("uploading");

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

      setUploadPhase("processing");

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response reader available");

      let buffer = ""; // Buffer for incomplete chunks

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        // Append new chunk to buffer and split by newlines
        buffer += new TextDecoder().decode(value);
        const lines = buffer.split("\n");

        // Keep the last incomplete line in the buffer
        buffer = lines.pop() || "";

        // Process complete lines
        for (const line of lines) {
          if (!line.trim()) continue;

          try {
            const data = JSON.parse(line);

            if (data.status === "error") {
              throw new Error(data.error);
            }

            if (data.status === "processing") {
              setProgress(data.progress);
              setProcessStats({
                processed: data.processed,
                total: data.total,
              });
            }

            if (data.status === "complete") {
              setElements(data.elements);
              setProgress(100);
            }
          } catch (parseError) {
            console.error("Error parsing JSON:", parseError);
            console.debug("Problematic line:", line);
          }
        }
      }

      // Process any remaining data in the buffer
      if (buffer.trim()) {
        try {
          const data = JSON.parse(buffer);
          if (data.status === "complete") {
            setElements(data.elements);
            setProgress(100);
          }
        } catch (parseError) {
          console.error("Error parsing final buffer:", parseError);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setElements([]);
    } finally {
      setLoading(false);
      setUploadPhase("idle");
    }
  };

  const getProgressMessage = () => {
    if (uploadPhase === "uploading") {
      return "Uploading IFC file...";
    }
    if (!processStats) {
      return "Preparing to process file...";
    }
    return `Processing: ${processStats.processed.toLocaleString()} / ${processStats.total.toLocaleString()} elements`;
  };

  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;

  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-bold mb-4">IFC Building Elements</h1>

      {/* Upload Section */}
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

      {/* Progress Section */}
      {loading && (
        <div className="mb-8">
          <div className="w-full bg-gray-200 rounded-full h-2.5 dark:bg-gray-700 mb-2">
            <div
              className={`h-2.5 rounded-full transition-all duration-300 ${
                uploadPhase === "uploading"
                  ? "bg-yellow-600 animate-pulse"
                  : "bg-blue-600"
              }`}
              style={{
                width: uploadPhase === "uploading" ? "100%" : `${progress}%`,
              }}
            ></div>
          </div>
          <div className="flex justify-between items-center text-sm text-gray-600 dark:text-gray-400">
            <div>
              <span className="font-mono">{getProgressMessage()}</span>
            </div>
            <div className="font-mono font-medium">
              {uploadPhase === "uploading" ? (
                <span className="animate-pulse">Uploading...</span>
              ) : (
                `${Math.round(progress)}%`
              )}
            </div>
          </div>
        </div>
      )}

      {/* Elements Table */}
      {elements.length > 0 ? (
        <div className="mt-8 overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Global ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Predefined Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Object Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Net Volume (m³)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Gross Volume (m³)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Net Area (m²)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Gross Area (m²)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Load Bearing
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  External
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Materials
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Length (m)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Width (m)
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider">
                  Height (m)
                </th>
              </tr>
            </thead>
            <tbody className="bg-white dark:bg-gray-900 divide-y divide-gray-200 dark:divide-gray-700">
              {elements.map((element) => (
                <tr key={element.id}>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100 font-mono">
                    {element.globalId || "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.predefinedType || "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.objectType || "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.name || "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.netVolume
                      ? (element.netVolume / 1000000000).toFixed(3)
                      : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.grossVolume
                      ? (element.grossVolume / 1000000000).toFixed(3)
                      : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.netArea
                      ? (element.netArea / 1000000).toFixed(3)
                      : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.grossArea
                      ? (element.grossArea / 1000000).toFixed(3)
                      : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.loadBearing === null
                      ? "-"
                      : element.loadBearing
                      ? "Yes"
                      : "No"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.isExternal === null
                      ? "-"
                      : element.isExternal
                      ? "Yes"
                      : "No"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 dark:text-gray-100">
                    <ul>
                      {element.materials.map((material, index) => (
                        <li key={index}>
                          {material.name}:{" "}
                          {(material.volume / 1000000000).toFixed(3)}m³ (
                          {(material.fraction * 100).toFixed(1)}%)
                        </li>
                      ))}
                    </ul>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.length ? (element.length / 1000).toFixed(3) : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.width ? (element.width / 1000).toFixed(3) : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-gray-100">
                    {element.height ? (element.height / 1000).toFixed(3) : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center text-gray-500">
          Upload an IFC file to view elements
        </div>
      )}
    </main>
  );
}
