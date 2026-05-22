import { NextRequest, NextResponse } from "next/server";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(
  request: NextRequest,
  { params }: { params: { gate: string; job_id: string } }
) {
  const body = await request.json();
  const { gate, job_id } = params;

  const res = await fetch(`${API_BASE}/api/pipeline/hitl/${gate}/${job_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
