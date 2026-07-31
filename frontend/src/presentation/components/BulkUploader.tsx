import { useState } from 'react';
import { UploadCloud, CheckCircle2, FileSpreadsheet } from 'lucide-react';

interface BulkUploaderProps {
  onUpload: (file: File) => Promise<void>;
}

export function BulkUploader({ onUpload }: BulkUploaderProps) {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setSuccessMessage(null);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsUploading(true);
    try {
      await onUpload(file);
      setSuccessMessage(`Archivo ${file.name} procesado correctamente.`);
      setFile(null);
    } catch {
      setSuccessMessage('Error al procesar el archivo.');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="bg-slate-900/40 p-8 rounded-xl border border-slate-800 space-y-6 max-w-xl mx-auto text-center">
      <div className="border-2 border-dashed border-slate-700 hover:border-indigo-500/50 p-8 rounded-xl transition-colors bg-slate-950/50 flex flex-col items-center justify-center">
        <UploadCloud className="w-12 h-12 text-indigo-400 mb-3" />
        <h3 className="font-bold text-slate-200">Cargar Archivo de Leads</h3>
        <p className="text-xs text-slate-400 mt-1 mb-4">Soporta formatos .CSV o .XLSX hasta 10MB</p>

        <label className="bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium px-4 py-2 rounded-lg cursor-pointer transition-colors">
          Seleccionar Archivo
          <input type="file" accept=".csv, .xlsx" onChange={handleFileChange} className="hidden" />
        </label>
      </div>

      {file && (
        <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 flex items-center justify-between text-left">
          <div className="flex items-center gap-3">
            <FileSpreadsheet className="w-6 h-6 text-emerald-400" />
            <div>
              <p className="text-sm font-medium text-slate-200">{file.name}</p>
              <p className="text-xs text-slate-500 font-mono">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
          </div>

          <button
            onClick={handleUpload}
            disabled={isUploading}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            {isUploading ? 'Procesando...' : 'Iniciar Carga'}
          </button>
        </div>
      )}

      {successMessage && (
        <div className="flex items-center justify-center gap-2 text-emerald-400 text-sm bg-emerald-500/10 p-3 rounded-lg border border-emerald-500/20">
          <CheckCircle2 className="w-4 h-4" />
          <span>{successMessage}</span>
        </div>
      )}
    </div>
  );
}
