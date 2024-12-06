"use client";

import { useEffect, useState } from "react";
import { IFCElement } from "./types/elements";

export default function Home() {
  const [elements, setElements] = useState<IFCElement[]>([]);
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
      if (!data.elements) {
        throw new Error("No elements data received from server");
      }
      setElements(data.elements);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
      setElements([]); // Reset elements on error
    } finally {
      setLoading(false);
    }
  };

  if (error) return <div className="p-4 text-red-500">Error: {error}</div>;

  return (
    <main className="p-4">
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

      {/* Loading Indicator */}
      {loading && (
        <div className="text-center mb-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div>
          <p className="mt-2">Processing IFC file...</p>
        </div>
      )}

      {/* Elements Table */}
      {elements.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-full bg-white border border-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ID
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Net Volume
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Gross Volume
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Materials
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {elements.map((element) => (
                <tr key={element.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {element.id}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                    {element.type}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {element.name || "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {typeof element.netVolume === "number"
                      ? `${element.netVolume.toFixed(2)} m³`
                      : "-"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {typeof element.grossVolume === "number"
                      ? `${element.grossVolume.toFixed(2)} m³`
                      : "-"}
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    <div className="space-y-1">
                      {element.materials.map((material, idx) => (
                        <div key={idx}>
                          {material.name}: {material.volume.toFixed(2)} m³ (
                          {(material.fraction * 100).toFixed(1)}%)
                        </div>
                      ))}
                    </div>
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
