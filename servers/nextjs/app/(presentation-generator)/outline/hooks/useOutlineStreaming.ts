import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { toast } from "sonner";
import { setOutlines, SlideOutline } from "@/store/slices/presentationGeneration";
import { jsonrepair } from "jsonrepair";
import { StreamState } from "../types/index";
import { RootState } from "@/store/store";

const DEFAULT_STREAM_STATE: StreamState = {
  isStreaming: false,
  isLoading: true,
};

export const useOutlineStreaming = (presentationId: string | null) => {
  const dispatch = useDispatch();
  const { outlines } = useSelector((state: RootState) => state.presentationGeneration);
  const [streamState, setStreamState] = useState<StreamState>(DEFAULT_STREAM_STATE);

  useEffect(() => {
    console.log("useOutlineStreaming effect running:", { presentationId, outlines });
    if (!presentationId) return;
    
    // Check if we have valid outlines (with title/body) or just placeholder data
    const hasValidOutlines = outlines.length > 0 && outlines.some(outline => outline.title || outline.body);
    console.log("Has valid outlines:", hasValidOutlines);
    if (hasValidOutlines) return;

    let eventSource: EventSource;
    let accumulatedChunks = "";

    const initializeStream = async () => {
      setStreamState({ isStreaming: true, isLoading: true });

      try {
        eventSource = new EventSource(
          `/api/v1/ppt/outlines/stream?presentation_id=${presentationId}`
        );

        eventSource.addEventListener("response", (event) => {
          const data = JSON.parse(event.data);
          switch (data.type) {
            case "chunk":
              accumulatedChunks += data.chunk;
              try {
                const repairedJson = jsonrepair(accumulatedChunks);
                const partialData = JSON.parse(repairedJson);
                if (partialData.slides) {
                  dispatch(setOutlines(partialData.slides));
                  setStreamState(prev => ({ ...prev, isLoading: false }));
                }
              } catch (error) {
                // JSON isn't complete yet, continue accumulating
              }
              break;

            case "complete":
              try {
                console.log("Complete event received:", data);
                const outlinesData: SlideOutline[] = data.presentation.outlines;
                console.log("Outlines data:", outlinesData);
                dispatch(setOutlines(outlinesData));
                setStreamState({ isStreaming: false, isLoading: false });
                eventSource.close();
              } catch (error) {
                console.error("Error parsing complete event:", error);
                console.error("Complete event data:", data);
                toast.error("Failed to parse presentation data");
                eventSource.close();
              }
              accumulatedChunks = "";
              break;

            case "closing":
              setStreamState({ isStreaming: false, isLoading: false });
              eventSource.close();
              break;
            case "error":
              setStreamState({ isStreaming: false, isLoading: false });
              eventSource.close();
              toast.error('Error in outline streaming',
                {
                  description: data.detail || 'Failed to connect to the server. Please try again.',
                }
              );
              break;
          }
        });

        eventSource.onerror = () => {
          setStreamState({ isStreaming: false, isLoading: false });
          eventSource.close();
          toast.error("Failed to connect to the server. Please try again.");
        };
      } catch (error) {
        setStreamState({ isStreaming: false, isLoading: false });
        toast.error("Failed to initialize connection");
      }
    };

    initializeStream();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [presentationId, dispatch]);

  return streamState;
}; 