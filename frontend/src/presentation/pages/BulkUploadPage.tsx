import * as intakeService from '../../application/services/intake.service';
import * as intakeJobsService from '../../application/services/intake-jobs.service';
import { BulkUploader, type BulkUploadResult } from '../components/BulkUploader';

async function uploadAndWait(file: File): Promise<BulkUploadResult> {
  const accepted = await intakeService.batchUpload(file);
  const job = await intakeJobsService.waitForJob(accepted.job_id);
  return { succeeded: job.succeeded, failed: job.failed };
}

export function BulkUploadPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Carga Masiva de Leads</h2>
        <p className="text-sm text-slate-400">Importa archivos CSV o Excel para calificar y enrutar prospectos en lote.</p>
      </div>

      <BulkUploader onUpload={uploadAndWait} />
    </div>
  );
}
