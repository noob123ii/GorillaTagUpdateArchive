import React, { useState, useMemo, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { gorillaTagUpdates } from '@/data/gorillaTagUpdates';
import { Search, Download, ChevronDown, ExternalLink, Terminal, Cloud, Link2, Calendar, Settings, Volume2, VolumeX, Moon, Sun } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { motion, AnimatePresence } from 'framer-motion';
import { format } from 'date-fns';
import DownloadNotification from '@/components/gorilla/DownloadNotification';
import SettingsPanel from '@/components/gorilla/SettingsPanel';

const GORILLA_TAG_APP_ID = '1533390';
const GORILLA_TAG_DEPOT_ID = '1533391';

const usePreferences = () => {
  const [prefs, setPrefs] = useState(() => {
    const saved = localStorage.getItem('gt-prefs');
    return saved ? JSON.parse(saved) : {
      soundEnabled: true,
      compactMode: false,
      autoExpand: true,
      theme: 'dark'
    };
  });

  useEffect(() => {
    localStorage.setItem('gt-prefs', JSON.stringify(prefs));
  }, [prefs]);

  return [prefs, setPrefs];
};

const playClickSound = (enabled) => {
  if (!enabled) return;
  try {
    const audioContext = new (window.AudioContext || window.webkitURL.arguments.AudioContext())();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.setValueAtTime(600, audioContext.currentTime);
    oscillator.frequency.exponentialRampToValueAtTime(300, audioContext.currentTime + 0.08);
    
    gainNode.gain.setValueAtTime(0.15, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.08);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.08);
  } catch (e) {}
};

export default function Home() {
  const [searchQuery, setSearchQuery] = useState('');
  const [notification, setNotification] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [prefs, setPrefs] = usePreferences();
  
  const [expandedYears, setExpandedYears] = useState(() => {
    return prefs.autoExpand ? { 2025: true, 2024: true } : {};
  });

  const { data: updates = [], isLoading } = useQuery({
    queryKey: ['gorilla-updates'],
    queryFn: () => Promise.resolve(
      [...gorillaTagUpdates].sort((a, b) => (b.year || 0) - (a.year || 0))
    ),
  });

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type, id: Date.now() });
  };

  const filteredUpdates = useMemo(() => {
    if (!searchQuery) return updates;
    const query = searchQuery.toLowerCase();
    return updates.filter(u => 
      u.name?.toLowerCase().includes(query) ||
      u.version?.toLowerCase().includes(query) ||
      u.manifest_id?.includes(query)
    );
  }, [updates, searchQuery]);

  const updatesByYear = useMemo(() => {
    const grouped = {};
    filteredUpdates.forEach(update => {
      const year = update.year || 2025;
      if (!grouped[year]) grouped[year] = [];
      grouped[year].push(update);
    });
    return grouped;
  }, [filteredUpdates]);

  const sortedYears = Object.keys(updatesByYear).sort((a, b) => b - a);

  const toggleYear = (year) => {
    playClickSound(prefs.soundEnabled);
    setExpandedYears(prev => ({ ...prev, [year]: !prev[year] }));
  };

  const generateBatchScript = (update) => {
    const scriptContent = `@echo off
echo.
echo   Gorilla Tag Downloader - ${update.name}${update.version ? ` v${update.version}` : ''}
echo.
steamcmd +login anonymous +download_depot ${GORILLA_TAG_APP_ID} ${GORILLA_TAG_DEPOT_ID} ${update.manifest_id} +quit
echo.
echo   Done! Files in: steamapps\\content\\app_${GORILLA_TAG_APP_ID}\\depot_${GORILLA_TAG_DEPOT_ID}\\
pause`;

    const blob = new Blob([scriptContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `GorillaTag_${update.name.replace(/[^a-zA-Z0-9]/g, '_')}.bat`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDownload = (update) => {
    playClickSound(prefs.soundEnabled);
    
    if (update.download_type === 'steam_depot') {
      generateBatchScript(update);
      showNotification(`${update.name}${update.version ? ` v${update.version}` : ''} — Script ready`, 'success');
    } else if (update.download_url) {
      window.open(update.download_url, '_blank');
      showNotification(`Opening ${update.name}`, 'info');
    }
  };

  const getTypeIcon = (type) => {
    switch (type) {
      case 'google_drive': return Cloud;
      case 'direct_link': return Link2;
      default: return Terminal;
    }
  };

  const getReleaseTypeBadge = (releaseType) => {
    const styles = {
      beta: 'bg-amber-500/15 text-amber-300 border-amber-500/20',
      alpha: 'bg-rose-500/15 text-rose-300 border-rose-500/20',
      hotfix: 'bg-violet-500/15 text-violet-300 border-violet-500/20',
      flashback: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/20',
    };
    if (!releaseType || releaseType === 'stable') return null;
    return styles[releaseType] || null;
  };

  const expandAll = () => {
    const all = {};
    sortedYears.forEach(y => all[y] = true);
    setExpandedYears(all);
  };

  const collapseAll = () => {
    setExpandedYears({});
  };

  return (
    <div className="min-h-screen bg-[#07080a] text-white selection:bg-blue-500/30">
      <AnimatePresence>
        {notification && (
          <DownloadNotification
            key={notification.id}
            message={notification.message}
            type={notification.type}
            onComplete={() => setNotification(null)}
          />
        )}
      </AnimatePresence>

      {/* Background */}
      <div className="fixed inset-0 bg-gradient-to-br from-blue-950/20 via-transparent to-indigo-950/10 pointer-events-none" />
      <div className="fixed inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-blue-900/10 via-transparent to-transparent pointer-events-none" />
      
      <div className="relative max-w-3xl mx-auto px-6 sm:px-8 py-12 sm:py-16">
        {/* Header */}
        <header className="mb-12">
          <div className="flex items-center justify-between mb-8">
            <div className="h-px flex-1 bg-gradient-to-r from-blue-500/30 via-blue-400/10 to-transparent" />
            <div className="flex items-center gap-2 ml-4">
              <button 
                onClick={() => setPrefs(p => ({ ...p, soundEnabled: !p.soundEnabled }))}
                className="p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.04] transition-all group"
                title={prefs.soundEnabled ? 'Mute sounds' : 'Enable sounds'}
              >
                {prefs.soundEnabled ? (
                  <Volume2 className="w-4 h-4 text-blue-400/50 group-hover:text-blue-400/80 transition-colors" />
                ) : (
                  <VolumeX className="w-4 h-4 text-white/20 group-hover:text-white/40 transition-colors" />
                )}
              </button>
              <button 
                onClick={() => setIsSettingsOpen(true)}
                className="p-2.5 rounded-xl bg-white/[0.02] hover:bg-white/[0.05] border border-white/[0.04] transition-all group"
              >
                <Settings className="w-4 h-4 text-white/25 group-hover:text-white/50 transition-colors" />
              </button>
            </div>
          </div>
          
          <h1 className="text-4xl sm:text-5xl font-light tracking-tight text-white mb-2">
            Gorilla Tag
          </h1>
          <p className="text-base text-blue-400/40 font-light tracking-wide">
            Version Archive
          </p>
        </header>

        {/* Search */}
        <div className="mb-8">
          <div className="relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-blue-400/30" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search versions..."
              className="pl-11 h-12 bg-white/[0.02] border-white/[0.05] text-white placeholder:text-white/20 rounded-xl focus:border-blue-500/30 focus:ring-0 focus:bg-white/[0.04] transition-all text-sm"
            />
          </div>
        </div>

        {/* Stats & Controls */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-5 text-xs text-white/30">
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500/50" />
              {updates.length} versions
            </span>
            <span className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-white/20" />
              {sortedYears.length} years
            </span>
          </div>
          <div className="flex items-center gap-1">
            <button 
              onClick={expandAll}
              className="px-3 py-1.5 text-[11px] text-white/30 hover:text-white/60 hover:bg-white/[0.03] rounded-lg transition-all"
            >
              Expand all
            </button>
            <button 
              onClick={collapseAll}
              className="px-3 py-1.5 text-[11px] text-white/30 hover:text-white/60 hover:bg-white/[0.03] rounded-lg transition-all"
            >
              Collapse
            </button>
          </div>
        </div>

        {/* Updates List */}
        {isLoading ? (
          <div className="flex items-center justify-center py-32">
            <div className="w-5 h-5 border-2 border-blue-500/20 border-t-blue-400 rounded-full animate-spin" />
          </div>
        ) : sortedYears.length === 0 ? (
          <div className="text-center py-32">
            <p className="text-white/25 text-sm">
              {searchQuery ? 'No versions match your search' : 'No versions available'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {sortedYears.map(year => {
              const isExpanded = expandedYears[year];
              const yearUpdates = updatesByYear[year];
              
              return (
                <div key={year} className="rounded-2xl bg-white/[0.01] border border-white/[0.03] overflow-hidden">
                  <button
                    onClick={() => toggleYear(year)}
                    className="w-full flex items-center justify-between px-5 py-4 group hover:bg-white/[0.02] transition-colors"
                  >
                    <div className="flex items-baseline gap-3">
                      <span className="text-xl font-medium text-white/80 group-hover:text-white transition-colors">
                        {year}
                      </span>
                      <span className="text-[11px] text-blue-400/40 tabular-nums">
                        {yearUpdates.length} {yearUpdates.length === 1 ? 'version' : 'versions'}
                      </span>
                    </div>
                    <motion.div
                      animate={{ rotate: isExpanded ? 180 : 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <ChevronDown className="w-4 h-4 text-white/20 group-hover:text-white/40 transition-colors" />
                    </motion.div>
                  </button>

                  <AnimatePresence>
                    {isExpanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
                        className="overflow-hidden"
                      >
                        <div className="px-3 pb-3 space-y-1">
                          {yearUpdates.map((update, index) => {
                            const TypeIcon = getTypeIcon(update.download_type);
                            const badgeStyle = getReleaseTypeBadge(update.release_type);
                            
                            return (
                              <motion.div
                                key={update.id || index}
                                initial={{ opacity: 0, y: 4 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: index * 0.02 }}
                                className={`group/row flex items-center gap-4 p-3 rounded-xl hover:bg-blue-500/[0.06] border border-transparent hover:border-blue-500/10 transition-all cursor-pointer ${prefs.compactMode ? 'py-2' : 'py-3'}`}
                                onClick={() => handleDownload(update)}
                              >
                                {/* Type Icon */}
                                <div className={`${prefs.compactMode ? 'w-8 h-8' : 'w-10 h-10'} rounded-xl bg-blue-500/8 flex items-center justify-center flex-shrink-0 group-hover/row:bg-blue-500/15 transition-colors border border-blue-500/10`}>
                                  <TypeIcon className={`${prefs.compactMode ? 'w-3.5 h-3.5' : 'w-4 h-4'} text-blue-400/80`} />
                                </div>
                                
                                {/* Content */}
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2.5 flex-wrap">
                                    <span className={`${prefs.compactMode ? 'text-xs' : 'text-sm'} text-white/80 group-hover/row:text-white transition-colors font-medium tracking-tight`}>
                                      {update.name}
                                    </span>
                                    
                                    {update.version && (
                                      <span className="text-[11px] text-blue-300/50 bg-blue-500/10 px-2 py-0.5 rounded-md font-medium">
                                        v{update.version}
                                      </span>
                                    )}
                                    
                                    {badgeStyle && (
                                      <span className={`text-[9px] uppercase tracking-wider px-1.5 py-0.5 rounded border font-medium ${badgeStyle}`}>
                                        {update.release_type}
                                      </span>
                                    )}
                                  </div>
                                  
                                  {!prefs.compactMode && (
                                    <div className="flex items-center gap-4 text-xs text-white/25 mt-1">
                                      {update.release_date && (
                                        <span className="flex items-center gap-1.5">
                                          <Calendar className="w-3 h-3" />
                                          {format(new Date(update.release_date), 'MMM d, yyyy')}
                                        </span>
                                      )}
                                      
                                      {update.manifest_id && (
                                        <span className="font-mono text-white/15 hidden sm:block truncate max-w-[180px]">
                                          {update.manifest_id}
                                        </span>
                                      )}
                                    </div>
                                  )}
                                </div>
                                
                                {/* Download */}
                                <div className={`${prefs.compactMode ? 'w-8 h-8' : 'w-10 h-10'} rounded-xl bg-blue-500/5 group-hover/row:bg-blue-500/20 flex items-center justify-center transition-all flex-shrink-0 border border-transparent group-hover/row:border-blue-500/20`}>
                                  {update.download_type === 'steam_depot' ? (
                                    <Download className={`${prefs.compactMode ? 'w-3.5 h-3.5' : 'w-4 h-4'} text-blue-400/40 group-hover/row:text-blue-300 transition-colors`} />
                                  ) : (
                                    <ExternalLink className={`${prefs.compactMode ? 'w-3.5 h-3.5' : 'w-4 h-4'} text-blue-400/40 group-hover/row:text-blue-300 transition-colors`} />
                                  )}
                                </div>
                              </motion.div>
                            );
                          })}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        )}

        {/* Footer */}
        <footer className="mt-20 pt-6 border-t border-white/[0.03]">
          <p className="text-[10px] text-white/15 leading-relaxed">
            Community archive · Not affiliated with Another Axiom
          </p>
        </footer>
      </div>

      <SettingsPanel 
        isOpen={isSettingsOpen} 
        onClose={() => setIsSettingsOpen(false)}
        prefs={prefs}
        setPrefs={setPrefs}
      />
    </div>
  );
}