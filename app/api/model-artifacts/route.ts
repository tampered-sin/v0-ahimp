import { NextResponse } from "next/server"
import { access, readFile } from "node:fs/promises"
import path from "node:path"

type JsonObject = Record<string, unknown>

async function readJsonIfExists(filePath: string): Promise<JsonObject | null> {
  try {
    await access(filePath)
    const raw = await readFile(filePath, "utf-8")
    return JSON.parse(raw) as JsonObject
  } catch {
    return null
  }
}

export async function GET() {
  const root = process.cwd()

  const lightgbmBenchmarkPath = path.join(root, "backend", "benchmark_results.json")
  const catboostBenchmarkPath = path.join(root, "backend", "benchmark_results_catboost.json")
  const bestParamsPath = path.join(root, "backend", "models", "best_params.json")

  const [lightgbmBenchmark, catboostBenchmark, bestParams] = await Promise.all([
    readJsonIfExists(lightgbmBenchmarkPath),
    readJsonIfExists(catboostBenchmarkPath),
    readJsonIfExists(bestParamsPath),
  ])

  return NextResponse.json({
    generated_at: new Date().toISOString(),
    benchmarks: {
      lightgbm: lightgbmBenchmark,
      catboost: catboostBenchmark,
    },
    tuning: bestParams,
  })
}
