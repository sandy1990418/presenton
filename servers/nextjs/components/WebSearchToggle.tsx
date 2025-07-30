'use client';

import React, { useState, useEffect } from 'react';
import { Search, Globe, Info } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';

interface WebSearchToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  className?: string;
}

export const WebSearchToggle: React.FC<WebSearchToggleProps> = ({
  enabled,
  onChange,
  className = ""
}) => {
  const [showInfo, setShowInfo] = useState(false);

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      {/* Toggle Switch */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-gray-600" />
          <span className="text-sm font-medium text-gray-700">Web Search</span>
        </div>
        
        <button
          onClick={() => onChange(!enabled)}
          className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 ${
            enabled ? 'bg-blue-600' : 'bg-gray-200'
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
              enabled ? 'translate-x-6' : 'translate-x-1'
            }`}
          />
        </button>
      </div>

      {/* Info Popover */}
      <Popover open={showInfo} onOpenChange={setShowInfo}>
        <PopoverTrigger asChild>
          <button className="text-gray-400 hover:text-gray-600 transition-colors">
            <Info className="w-4 h-4" />
          </button>
        </PopoverTrigger>
        <PopoverContent className="w-80 p-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Search className="w-5 h-5 text-blue-600" />
              <h4 className="font-semibold text-gray-900">Web Search Integration</h4>
            </div>
            
            <div className="text-sm text-gray-600 space-y-2">
              <p>
                When enabled, the AI can search the web for current information, statistics, 
                and recent developments to enhance your presentation content.
              </p>
              
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <p className="font-medium text-blue-800 mb-1">Useful for:</p>
                <ul className="text-blue-700 text-xs space-y-1">
                  <li>• Current market data and statistics</li>
                  <li>• Recent news and developments</li>
                  <li>• Up-to-date research and studies</li>
                  <li>• Latest trends and insights</li>
                </ul>
              </div>
              
              <p className="text-xs text-gray-500">
                <strong>Note:</strong> Web search may increase generation time but provides 
                more current and accurate information.
              </p>
            </div>
          </div>
        </PopoverContent>
      </Popover>
      
      {/* Status Indicator */}
      {enabled && (
        <div className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs">
          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          Active
        </div>
      )}
    </div>
  );
};

export default WebSearchToggle;