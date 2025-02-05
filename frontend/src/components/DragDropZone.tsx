import React, { useCallback } from 'react';
import { FileUp } from 'lucide-react';

interface DragDropZoneProps {
  onFileUpload: (file: File) => void;
}

export const DragDropZone: React.FC<DragDropZoneProps> = ({ onFileUpload }) => {
  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file && file.type === 'application/pdf') {
        onFileUpload(file);
      }
    },
    [onFileUpload]
  );

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-500 transition-colors cursor-pointer"
    >
      <FileUp className="w-12 h-12 mx-auto mb-4 text-gray-400" />
      <p className="text-lg text-gray-600">Drag and drop your PDF here</p>
      <p className="text-sm text-gray-400 mt-2">or click to select a file</p>
    </div>
  );
};