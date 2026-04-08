"use client"

import { useEffect, useMemo, useState } from "react"
import { Building2, Sparkles } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { SupplyChainDecision } from "@/lib/ml-api"

interface SupplierRecommendationsProps {
  decisions: SupplyChainDecision[]
}

export function SupplierRecommendations({ decisions }: SupplierRecommendationsProps) {
  const sorted = useMemo(() => {
    return [...decisions].sort(
      (left, right) => right.recommended_supplier.score - left.recommended_supplier.score
    )
  }, [decisions])

  const [selectedItemId, setSelectedItemId] = useState<number | null>(null)

  useEffect(() => {
    setSelectedItemId(sorted[0]?.item_id ?? null)
  }, [sorted])

  const selected = useMemo(() => {
    return sorted.find((decision) => decision.item_id === selectedItemId) ?? sorted[0] ?? null
  }, [selectedItemId, sorted])

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="size-4" />
          Supplier Recommendations
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {sorted.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            Run at-risk analysis to view supplier recommendations.
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {sorted.slice(0, 6).map((decision) => (
                <button
                  key={decision.item_id}
                  onClick={() => setSelectedItemId(decision.item_id)}
                  className="w-full rounded-md border border-border p-2 text-left transition-colors hover:bg-muted/30 data-[active=true]:border-primary"
                  data-active={selected?.item_id === decision.item_id}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-medium">{decision.recommended_supplier.supplier_name}</p>
                      <p className="text-xs text-muted-foreground">for {decision.item_name}</p>
                    </div>
                    <Badge variant="outline">{decision.recommended_supplier.score.toFixed(2)}</Badge>
                  </div>
                </button>
              ))}
            </div>

            {selected && (
              <div className="rounded-lg border border-border bg-muted/20 p-3">
                <div className="mb-2 flex items-center gap-2">
                  <Building2 className="size-4 text-primary" />
                  <h4 className="text-sm font-semibold">Recommendation Details</h4>
                </div>
                <p className="text-sm font-medium">{selected.recommended_supplier.supplier_name}</p>
                <p className="text-xs text-muted-foreground">
                  Supplier #{selected.recommended_supplier.supplier_id} • Score {selected.recommended_supplier.score.toFixed(2)}
                </p>
                <p className="mt-2 text-xs text-muted-foreground">{selected.reason}</p>

                {selected.recommended_supplier.breakdown && (
                  <div className="mt-3 grid grid-cols-2 gap-2">
                    {Object.entries(selected.recommended_supplier.breakdown).map(([key, value]) => (
                      <div key={key} className="rounded-md border border-border bg-background px-2 py-1 text-xs">
                        <p className="text-muted-foreground">{key.replaceAll("_", " ")}</p>
                        <p className="font-semibold">{value.toFixed(3)}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  )
}
