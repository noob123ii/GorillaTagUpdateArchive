import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Check, Download, Info } from 'lucide-react';

function DownloadNotification({ message, type = 'info', onComplete, duration = 4000 }) {
  const [progress, setProgress] = useState(100);

  useEffect(() => {
    const startTime = Date.now();
    const interval = setInterval(() => {
      const elapsed = Date.now() - startTime;
      const remaining = Math.max(0, 100 - (elapsed / duration) * 100);
      setProgress(remaining);
      
      if (remaining <= 0) {
        clearInterval(interval);
        onComplete?.();
      }
    }, 16);

    return () => clearInterval(interval);
  }, [duration, onComplete]);

  const icons = {
    success: Check,
    info: Info,
    download: Download
  };

  const Icon = icons[type] || icons.info;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, x: 0 }}
      animate={{ opacity: 1, y: 0, x: 0 }}
      exit={{ opacity: 0, y: 20, x: 0 }}
      transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
      className="fixed bottom-6 left-6 z-50 w-[90%] max-w-xs"
    >
      <div className="relative overflow-hidden bg-[#0c0c10] border border-blue-500/10 rounded-xl shadow-2xl shadow-black/50">
        <div className="flex items-center gap-3 px-4 py-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/15 flex items-center justify-center flex-shrink-0">
            <Icon className="w-4 h-4 text-blue-400" />
          </div>
          <p className="text-sm text-white/70">{message}</p>
        </div>
        
        <div className="h-[2px] bg-white/[0.02]">
          <motion.div
            className="h-full bg-gradient-to-r from-blue-500 to-blue-400"
            initial={{ width: '100%' }}
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.016, ease: 'linear' }}
          />
        </div>
      </div>
    </motion.div>
  );
}

export default DownloadNotification;