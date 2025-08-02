import React from 'react';

interface Citation {
  domain: string;
  url: string;
  title: string;
  queries?: string[];
  relevance_score?: number;
}

interface CitationDisplayProps {
  citations: Citation[];
  showFullDetails?: boolean;
  className?: string;
}

const CitationDisplay: React.FC<CitationDisplayProps> = ({ 
  citations, 
  showFullDetails = false, 
  className = '' 
}) => {
  if (!citations || citations.length === 0) {
    return null;
  }

  if (showFullDetails) {
    return (
      <div className={`citation-details ${className}`}>
        <h4 className="text-sm font-semibold text-gray-700 mb-2">Sources:</h4>
        <div className="space-y-1">
          {citations.map((citation, index) => (
            <div key={index} className="flex items-center space-x-2">
              <span className="text-xs text-gray-500">•</span>
              <a
                href={citation.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-blue-600 hover:text-blue-800 hover:underline"
                title={citation.title}
              >
                {citation.domain}
              </a>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Compact footer display (like the screenshot shows)
  return (
    <div className={`citation-footer ${className}`}>
      <div className="flex items-center justify-center space-x-4 text-xs text-gray-500">
        {citations.slice(0, 3).map((citation, index) => (
          <React.Fragment key={index}>
            {index > 0 && <span>•</span>}
            <a
              href={citation.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-700 transition-colors duration-200"
              title={`Visit ${citation.domain} - ${citation.title}`}
            >
              {citation.domain}
            </a>
          </React.Fragment>
        ))}
        {citations.length > 3 && (
          <>
            <span>•</span>
            <span title={`${citations.length - 3} more sources`}>
              +{citations.length - 3} more
            </span>
          </>
        )}
      </div>
    </div>
  );
};

export default CitationDisplay;