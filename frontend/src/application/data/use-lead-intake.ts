import { useState } from 'react';
import * as intakeService from '../services/intake.service';
import * as intakeJobsService from '../services/intake-jobs.service';
import * as leadsService from '../services/leads.service';
import * as agentsService from '../services/agents.service';
import type { IngestLeadRequest } from '../services/intake.service';
import type { components } from '../../infrastructure/api/intake-schema';
import { LeadStatus, type LeadModel } from '../../domain/lead.model';

export type IntakeError = components['schemas']['IntakeErrorResponse'];

export type LeadIntakeOutcome =
  | { kind: 'assigned'; lead: LeadModel; agentName: string }
  | { kind: 'unassigned'; lead: LeadModel }
  | { kind: 'disqualified'; lead: LeadModel }
  | { kind: 'rejected'; errors: IntakeError[] };

export interface LeadIntakeState {
  submitting: boolean;
  outcome: LeadIntakeOutcome | null;
  error: unknown;
  submit: (body: IngestLeadRequest) => Promise<void>;
}

/**
 * Drives the full cycle a single ingested lead goes through after the 202:
 * poll its job to a terminal state, read the record it produced to tell a
 * rejected payload from a promoted one, and for a promoted lead resolve where
 * it actually landed — assigned, unassigned, or disqualified.
 */
export function useLeadIntake(): LeadIntakeState {
  const [submitting, setSubmitting] = useState(false);
  const [outcome, setOutcome] = useState<LeadIntakeOutcome | null>(null);
  const [error, setError] = useState<unknown>(null);

  async function submit(body: IngestLeadRequest): Promise<void> {
    setSubmitting(true);
    setError(null);
    setOutcome(null);
    try {
      const accepted = await intakeService.ingest(body);
      const job = await intakeJobsService.waitForJob(accepted.job_id);
      const records = await intakeService.listRecords(1, 0, { jobId: job.id });
      const record = records.items.find((r) => r.id === accepted.record_ids[0]) ?? records.items[0];

      if (!record || record.status !== 'PROMOTED' || !record.lead_id) {
        setOutcome({ kind: 'rejected', errors: record?.errors ?? [] });
        return;
      }

      const lead = await leadsService.get(record.lead_id);
      if (lead.status === LeadStatus.DISQUALIFIED) {
        setOutcome({ kind: 'disqualified', lead });
      } else if (lead.status === LeadStatus.ASSIGNED && lead.assignedAgentId) {
        const agent = await agentsService.get(lead.assignedAgentId);
        setOutcome({ kind: 'assigned', lead, agentName: agent.name });
      } else {
        setOutcome({ kind: 'unassigned', lead });
      }
    } catch (err) {
      setError(err);
    } finally {
      setSubmitting(false);
    }
  }

  return { submitting, outcome, error, submit };
}
