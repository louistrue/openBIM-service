import { NextResponse } from "next/server";
import { IFCElement } from "@/app/types/elements";

// Add caching headers
const CACHE_CONTROL = "public, s-maxage=10, stale-while-revalidate=59";

export async function GET() {
  try {
    // This will be replaced with actual data from the backend
    return NextResponse.json([], {
      headers: {
        "Cache-Control": CACHE_CONTROL,
      },
    });
  } catch (error) {
    console.error("Error fetching elements:", error);
    return NextResponse.json(
      { error: "Failed to fetch elements" },
      {
        status: 500,
        headers: {
          "Cache-Control": "no-store",
        },
      }
    );
  }
}
