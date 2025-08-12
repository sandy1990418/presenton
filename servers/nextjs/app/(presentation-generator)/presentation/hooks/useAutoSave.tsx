'use client'
import { useEffect, useRef, useCallback, useState } from 'react';
import { useSelector } from 'react-redux';
import { RootState } from '@/store/store';
import { PresentationGenerationApi } from '../../services/api/presentation-generation';

interface UseAutoSaveOptions {
    debounceMs?: number;
    enabled?: boolean;
}

export const useAutoSave = ({
    debounceMs = 2000,
    enabled = true,
}: UseAutoSaveOptions = {}) => {
    const { presentationData, isStreaming, isLoading, isLayoutLoading } = useSelector(
        (state: RootState) => state.presentationGeneration
    );

    const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const lastSavedDataRef = useRef<string>('');
    const [isSaving, setIsSaving] = useState<boolean>(false);

    // Debounced save function
    const debouncedSave = useCallback(async (data: any) => {
        // Clear existing timeout
        if (saveTimeoutRef.current) {
            clearTimeout(saveTimeoutRef.current);
        }

        // Set new timeout
        saveTimeoutRef.current = setTimeout(async () => {
            if (!data || isSaving) return;

            const currentDataString = JSON.stringify(data);

            // Skip if data hasn't changed since last save
            if (currentDataString === lastSavedDataRef.current) {
                return;
            }

            try {
                setIsSaving(true);
                console.log('🔄 Auto-saving presentation data...');
                console.log('📊 Original data structure:', JSON.stringify(data, null, 2));

                // Transform data to match backend PresentationWithSlides model
                const transformedData = {
                    id: data.id,
                    prompt: data.prompt || "", // Default empty string if missing
                    n_slides: data.n_slides,
                    language: data.language,
                    title: data.title,
                    outlines: data.outlines || null,
                    created_at: data.created_at || new Date().toISOString(),
                    updated_at: new Date().toISOString(), // Always update timestamp
                    layout: data.layout,
                    structure: data.structure || null,
                    slides: (data.slides || []).map((slide: any) => ({
                        ...slide,
                        speaker_note: slide.speaker_note || slide.content?.__speaker_note__ || "",
                        html_content: slide.html_content || null,
                        properties: slide.properties || null
                    }))
                };

                console.log('🔧 Transformed data structure:', JSON.stringify(transformedData, null, 2));

                // Call the API to update presentation content
                await PresentationGenerationApi.updatePresentationContent(transformedData);

                // Update last saved data reference
                lastSavedDataRef.current = currentDataString;

                console.log('✅ Auto-save successful');

            } catch (error) {
                console.error('❌ Auto-save failed:', error);

            } finally {
                setIsSaving(false);
            }
        }, debounceMs);
    }, [debounceMs, isSaving]);

    // Effect to trigger auto-save when presentation data changes
    useEffect(() => {
        if (!enabled || !presentationData || isStreaming || isLoading || isLayoutLoading) return;

        // Trigger debounced save
        debouncedSave(presentationData);

        // Cleanup timeout on unmount
        return () => {
            if (saveTimeoutRef.current) {
                clearTimeout(saveTimeoutRef.current);
            }
        };
    }, [presentationData, enabled, debouncedSave]);

    return {
        isSaving,
    };
}; 