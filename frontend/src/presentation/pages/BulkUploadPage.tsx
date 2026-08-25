import * as intakeService from '../../application/services/intake.service';
import * as intakeJobsService from '../../application/services/intake-jobs.service';
import { BulkUploader, type BulkUploadResult } from '../components/BulkUploader';

async function uploadAndWait(file: File): Promise<BulkUploadResult> {
  const accepted = await intakeService.batchUpload(file);
  const job = await intakeJobsService.waitForJob(accepted.job_id);

  if (job.status === 'FAILED') {
    throw new Error('El archivo no se pudo leer. Revisa que sea un CSV o XLSX válido.');
  }
  // Not an error, and above all not a retry: the file is already accepted and
  // every row is a durable record. Reporting a failure here had the manager
  // uploading the same file again, and every copy was queued for real.
  return { succeeded: job.succeeded, failed: job.failed, pending: intakeJobsService.stillRunning(job) };
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
