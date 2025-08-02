import { useState, useEffect } from 'react';
import { PresentationGenerationApi } from '../../services/api/presentation-generation';

interface Citation {
  domain: string;
  url: string;
  title: string;
  queries?: string[];
  relevance_score?: number;
}

interface CitationsData {
  success: boolean;
  presentationId: string;
  citations: Citation[];
  totalCitations: number;
  citationsFooter: string;
}

export const useCitations = (presentationId: string | null) => {
  const [citations, setCitations] = useState<Citation[]>([]);
  const [citationsFooter, setCitationsFooter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCitations = async () => {
    if (!presentationId) return;

    setLoading(true);
    setError(null);

    try {
      const data: CitationsData = await PresentationGenerationApi.getCitations(presentationId);
      
      if (data.success) {
        setCitations(data.citations || []);
        setCitationsFooter(data.citationsFooter || '');
      } else {
        setError('Failed to fetch citations');
      }
    } catch (err) {
      console.error('Error fetching citations:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      // Set empty state on error
      setCitations([]);
      setCitationsFooter('');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCitations();
  }, [presentationId]);

  return {
    citations,
    citationsFooter,
    loading,
    error,
    refetch: fetchCitations,
  };
};