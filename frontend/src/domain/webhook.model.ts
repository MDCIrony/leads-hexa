export enum WebhookEventType {
  LEAD_INGESTED = 'LEAD_INGESTED',
  LEAD_QUALIFIED = 'LEAD_QUALIFIED',
  LEAD_ASSIGNED = 'LEAD_ASSIGNED',
  PROCESSING_ERROR = 'PROCESSING_ERROR',
}

export interface WebhookConfigModel {
  id: string;
  tenantId: string;
  eventType: WebhookEventType;
  targetUrl: string;
  secretToken: string;
}
