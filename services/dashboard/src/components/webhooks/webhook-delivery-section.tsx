"use client";

import { Webhook } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface WebhookDelivery {
  url?: string;
  status?: string;
  attempts?: number;
  status_code?: number;
  delivered_at?: string;
  failed_at?: string;
  queued_at?: string;
}

interface WebhookDeliverySectionProps {
  webhookDelivery?: WebhookDelivery;
}

export function WebhookDeliverySection({ webhookDelivery }: WebhookDeliverySectionProps) {
  if (!webhookDelivery || !webhookDelivery.url) {
    return null;
  }

  const success = webhookDelivery.status === "delivered";
  const timestamp = webhookDelivery.delivered_at || webhookDelivery.failed_at || webhookDelivery.queued_at;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Webhook className="h-4 w-4" />
          Webhook Delivery
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="rounded-lg bg-muted/50 divide-y divide-border/50 overflow-hidden">
          <div className="px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={cn(
                  "w-2 h-2 rounded-full",
                  success ? "bg-emerald-400" : webhookDelivery.status === "queued" ? "bg-yellow-400" : "bg-red-400"
                )}
              />
              <div>
                <p className="text-sm">
                  {webhookDelivery.attempts ?? 1} attempt{(webhookDelivery.attempts ?? 1) > 1 ? "s" : ""}{" "}
                  {timestamp && (
                    <span className="text-muted-foreground">
                      {new Date(timestamp).toLocaleString("en-US", {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                        second: "2-digit",
                        hour12: false,
                      })}
                    </span>
                  )}
                </p>
                <p className="text-[11px] font-mono text-muted-foreground mt-0.5">
                  POST {webhookDelivery.url}
                </p>
              </div>
            </div>
            <div className="text-right">
              <span
                className={cn(
                  "inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium",
                  success
                    ? "bg-emerald-900/30 text-emerald-300"
                    : webhookDelivery.status === "queued"
                      ? "bg-yellow-900/30 text-yellow-300"
                      : "bg-red-900/30 text-red-300"
                )}
              >
                {webhookDelivery.status_code ?? webhookDelivery.status ?? "pending"}
              </span>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
