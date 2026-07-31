import { BulkUploader } from '../components/BulkUploader';

interface BulkUploadPageProps {
  onUpload: (file: File) => Promise<void>;
}

export function BulkUploadPage({ onUpload }: BulkUploadPageProps) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-100">Carga Masiva de Leads</h2>
        <p className="text-sm text-slate-400">Importa archivos CSV o Excel para calificar y enrutar prospectos en lote.</p>
      </div>

      <BulkUploader onUpload={onUpload} />
    </div>
  );
}
