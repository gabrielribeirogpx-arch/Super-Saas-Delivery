"use client";

import { type DragEvent, useEffect, useId, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024;

interface ImageUploadFieldProps {
  label: string;
  accept: string;
  instructions: string[];
  initialPreviewUrl?: string;
  onRemove?: () => void;
  onFileSelect?: (file: File | null) => void;
}

const formatBytes = (bytes: number) => {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const kb = bytes / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }
  return `${(kb / 1024).toFixed(1)} MB`;
};

export function ImageUploadField({
  label,
  accept,
  instructions,
  initialPreviewUrl,
  onRemove,
  onFileSelect,
}: ImageUploadFieldProps) {
  const inputId = useId();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localPreviewUrl, setLocalPreviewUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => {
    if (!selectedFile) {
      setLocalPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setLocalPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  const activePreviewUrl = localPreviewUrl ?? initialPreviewUrl ?? null;

  const acceptsImage = useMemo(() => accept.includes("image"), [accept]);

  const validateFile = (file: File) => {
    if (file.size > MAX_FILE_SIZE_BYTES) {
      return `Arquivo muito grande (${formatBytes(file.size)}). Limite de 2MB.`;
    }

    const acceptedFormats = accept
      .split(",")
      .map((format) => format.trim())
      .filter(Boolean);

    const hasAcceptedMimeType = acceptedFormats.some((format) => {
      if (format.endsWith("/*")) {
        return file.type.startsWith(format.replace("*", ""));
      }
      return file.type === format;
    });

    if (!hasAcceptedMimeType) {
      return "Formato inválido. Selecione um arquivo no formato permitido.";
    }

    return null;
  };

  const handleFileChange = (file: File | null) => {
    if (!file) {
      setSelectedFile(null);
      setErrorMessage(null);
      onFileSelect?.(null);
      return;
    }

    const validationError = validateFile(file);
    if (validationError) {
      setSelectedFile(null);
      setErrorMessage(validationError);
      onFileSelect?.(null);
      return;
    }

    setSelectedFile(file);
    setErrorMessage(null);
    onFileSelect?.(file);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    const droppedFile = event.dataTransfer.files?.[0] ?? null;
    handleFileChange(droppedFile);
  };

  const handleRemove = () => {
    setSelectedFile(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    onFileSelect?.(null);
    onRemove?.();
  };

  return (
    <div className="space-y-3">
      <label htmlFor={inputId} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      <div
        className={`rounded-xl border border-dashed border-gray-300 p-4 transition-all duration-150 hover:border-blue-400 hover:bg-blue-50 ${
          isDragging ? "border-blue-500 bg-blue-50" : ""
        }`}
        onDragOver={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          id={inputId}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
        />

        {activePreviewUrl ? (
          <div className="mb-4 overflow-hidden rounded-lg border border-slate-200 bg-white">
            {acceptsImage ? (
              <img src={activePreviewUrl} alt={`Preview de ${label}`} className="h-44 w-full object-cover" />
            ) : (
              <video src={activePreviewUrl} className="h-44 w-full object-cover" controls />
            )}
          </div>
        ) : (
          <p className="mb-4 text-sm text-slate-500">Arraste e solte aqui ou selecione um arquivo.</p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={() => fileInputRef.current?.click()}>
            Selecionar imagem
          </Button>
          <Button type="button" variant="ghost" onClick={handleRemove}>
            Remover
          </Button>
        </div>
      </div>

      <div className="space-y-1 text-xs text-slate-500">
        {instructions.map((instruction) => (
          <p key={instruction}>{instruction}</p>
        ))}
      </div>

      {errorMessage && <p className="text-sm font-medium text-red-600">{errorMessage}</p>}
    </div>
  );
}
