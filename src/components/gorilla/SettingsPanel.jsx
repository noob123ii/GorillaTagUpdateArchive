import React from 'react';
import { Volume2, VolumeX, Maximize2, Minimize2, ChevronDown, ChevronUp } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

function SettingsPanel({ isOpen, onClose, prefs, setPrefs }) {
  const togglePref = (key) => {
    setPrefs(prev => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#0a0b0e] border-blue-500/10 text-white max-w-sm p-0 gap-0 overflow-hidden">
        <DialogHeader className="p-5 pb-3 border-b border-white/[0.04]">
          <DialogTitle className="text-base font-medium text-white/90">
            Preferences
          </DialogTitle>
        </DialogHeader>

        <div className="p-5 space-y-1">
          {/* Sound */}
          <div 
            className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.02] transition-colors cursor-pointer"
            onClick={() => togglePref('soundEnabled')}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                {prefs.soundEnabled ? (
                  <Volume2 className="w-4 h-4 text-blue-400/70" />
                ) : (
                  <VolumeX className="w-4 h-4 text-white/30" />
                )}
              </div>
              <div>
                <p className="text-sm text-white/80">Sound effects</p>
                <p className="text-[11px] text-white/30">Click sounds on actions</p>
              </div>
            </div>
            <Switch 
              checked={prefs.soundEnabled} 
              onCheckedChange={() => togglePref('soundEnabled')}
              className="data-[state=checked]:bg-blue-500"
            />
          </div>

          {/* Compact Mode */}
          <div 
            className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.02] transition-colors cursor-pointer"
            onClick={() => togglePref('compactMode')}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                {prefs.compactMode ? (
                  <Minimize2 className="w-4 h-4 text-blue-400/70" />
                ) : (
                  <Maximize2 className="w-4 h-4 text-white/30" />
                )}
              </div>
              <div>
                <p className="text-sm text-white/80">Compact mode</p>
                <p className="text-[11px] text-white/30">Smaller list items</p>
              </div>
            </div>
            <Switch 
              checked={prefs.compactMode} 
              onCheckedChange={() => togglePref('compactMode')}
              className="data-[state=checked]:bg-blue-500"
            />
          </div>

          {/* Auto Expand */}
          <div 
            className="flex items-center justify-between p-3 rounded-xl hover:bg-white/[0.02] transition-colors cursor-pointer"
            onClick={() => togglePref('autoExpand')}
          >
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-blue-500/10 flex items-center justify-center">
                {prefs.autoExpand ? (
                  <ChevronDown className="w-4 h-4 text-blue-400/70" />
                ) : (
                  <ChevronUp className="w-4 h-4 text-white/30" />
                )}
              </div>
              <div>
                <p className="text-sm text-white/80">Auto-expand years</p>
                <p className="text-[11px] text-white/30">Show recent years on load</p>
              </div>
            </div>
            <Switch 
              checked={prefs.autoExpand} 
              onCheckedChange={() => togglePref('autoExpand')}
              className="data-[state=checked]:bg-blue-500"
            />
          </div>
        </div>

        <div className="p-5 pt-2 border-t border-white/[0.04]">
          <Button
            onClick={onClose}
            className="w-full h-10 bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/20 text-blue-300 hover:text-blue-200 rounded-xl text-sm"
          >
            Done
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export default SettingsPanel;