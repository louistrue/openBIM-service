import { NextResponse } from "next/server";
import { IFCElement } from "@/app/types/elements";

export async function GET() {
  try {
    // This will be replaced with actual data from the backend
    return NextResponse.json([]);
  } catch (error) {
    return NextResponse.json(
      { error: "Failed to fetch elements" },
      { status: 500 }
    );
  }
}
