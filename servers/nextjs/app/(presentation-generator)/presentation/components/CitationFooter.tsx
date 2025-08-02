import React from 'react';
import { useCitations } from '../hooks/useCitations';

interface CitationFooterProps {
  presentationId: string;
  className?: string;
  theme?: 'light' | 'dark';
}

const CitationFooter: React.FC<CitationFooterProps> = ({ 
  presentationId, 
  className = '',
  theme = 'light'
}) => {
  const { citations, loading, error } = useCitations(presentationId);

  // Don't render if no citations, still loading, or error
  if (loading || error || !citations || citations.length === 0) {
    return null;
  }

  // Theme styles to match screenshot
  const themeStyles = theme === 'dark' 
    ? 'bg-gray-800 text-gray-300' 
    : 'bg-gray-50 text-gray-600';

  return (
    <div className={`citation-footer border-t ${themeStyles} px-4 py-2 ${className}`}>
      <div className="flex items-center justify-center space-x-2 text-xs">
        {citations.slice(0, 3).map((citation, index) => (
          <React.Fragment key={citation.url}>
            {index > 0 && <span className="text-gray-400 mx-1">•</span>}
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 hover:underline transition-colors duration-200 font-medium"
              title={`Visit ${citation.domain} - ${citation.title}`}
            >
              {citation.domain}
            </a>
          </React.Fragment>
        ))}
        {citations.length > 3 && (
          <>
            <span className="text-gray-400 mx-1">•</span>
            <span 
              className="text-gray-500 font-medium"
              title={`${citations.length - 3} more sources: ${citations.slice(3).map(c => c.domain).join(', ')}`}
            >
              +{citations.length - 3}
            </span>
          </>
        )}
      </div>
    </div>
  );
};

export default CitationFooter;