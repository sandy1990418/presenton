// import { useEffect, useRef } from "react";
// import { useDispatch, useSelector } from "react-redux";
// import {
//   clearPresentationData,
//   setPresentationData,
//   setStreaming,
// } from "@/store/slices/presentationGeneration";
// import { jsonrepair } from "jsonrepair";
// import { toast } from "sonner";

// // Global state to prevent multiple streams across all components
// const globalStreamState = {
//   activeStreams: new Set<string>(),
//   isStreaming: (presentationId: string) => globalStreamState.activeStreams.has(presentationId),
//   startStream: (presentationId: string) => globalStreamState.activeStreams.add(presentationId),
//   endStream: (presentationId: string) => globalStreamState.activeStreams.delete(presentationId),
// };

// export const usePresentationStreaming = (
//   presentationId: string,
//   stream: string | null,
//   setLoading: (loading: boolean) => void,
//   setError: (error: boolean) => void,
//   fetchUserSlides: () => void
// ) => {
//   const dispatch = useDispatch();
//   const previousSlidesLength = useRef(0);
//   const eventSourceRef = useRef<EventSource | null>(null);
//   const timeoutRef = useRef<NodeJS.Timeout | null>(null);
//   const streamingRef = useRef<boolean>(false); // Prevent concurrent streams
//   const lastStreamedPresentationRef = useRef<string | null>(null); // Track last streamed presentation

//   useEffect(() => {
//     let accumulatedChunks = "";
//     const STREAM_TIMEOUT = 5 * 60 * 1000; // 5 minutes timeout

//     const cleanup = () => {
//       if (eventSourceRef.current) {
//         eventSourceRef.current.close();
//         eventSourceRef.current = null;
//       }
//       if (timeoutRef.current) {
//         clearTimeout(timeoutRef.current);
//         timeoutRef.current = null;
//       }
//       accumulatedChunks = "";
//       streamingRef.current = false; // Reset streaming flag
//       globalStreamState.endStream(presentationId); // Remove from global state
//     };

//     const initializeStream = async () => {
//       // Global check for active streams
//       if (globalStreamState.isStreaming(presentationId)) {
//         console.warn(`Global state: Stream already active for presentation ${presentationId}`);
//         return;
//       }
      
//       // Prevent concurrent streaming requests
//       if (streamingRef.current) {
//         console.warn("Local state: Stream already in progress, ignoring duplicate request");
//         return;
//       }
      
//       // Prevent re-streaming the same presentation
//       if (lastStreamedPresentationRef.current === presentationId) {
//         console.warn(`Cache: Presentation ${presentationId} already streamed, ignoring duplicate request`);
//         return;
//       }
      
//       console.log(`Starting stream for presentation ${presentationId}`);
//       cleanup(); // Ensure clean state
//       streamingRef.current = true;
//       lastStreamedPresentationRef.current = presentationId;
//       globalStreamState.startStream(presentationId);
      
//       dispatch(setStreaming(true));
//       dispatch(clearPresentationData());

//       // Set timeout for the entire streaming process
//       // timeoutRef.current = setTimeout(() => {
//       //   console.error('Stream timeout after 5 minutes');
//       //   cleanup();
//       //   setLoading(false);
//       //   dispatch(setStreaming(false));
//       //   setError(true);
//       // }, STREAM_TIMEOUT);

//       // eventSourceRef.current = new EventSource(
//       //   `/api/v1/ppt/presentation/stream?presentation_id=${presentationId}`
//       // );

//       // eventSourceRef.current.addEventListener("response", (event) => {
//       //   try {
//       //     const data = JSON.parse(event.data);

//       //     switch (data.type) {
//       //       case "status":
//       //         // Handle status messages for better user feedback
//       //         console.log("📊 Stream status:", data.status);
//       //         break;
              
//       //       case "error":
//       //         console.error("Stream error:", data.error);
//       //         cleanup();
//       //         setError(true);
//       //         setLoading(false);
//       //         dispatch(setStreaming(false));
//       //         break;
              
//       //       case "chunk":
//       //         accumulatedChunks += data.chunk;
              
//       //         // Limit accumulated chunks size to prevent memory issues
//       //         if (accumulatedChunks.length > 1024 * 1024) { // 1MB limit
//       //           console.warn("Accumulated chunks too large, resetting");
//       //           accumulatedChunks = data.chunk;
//       //         }
              
//       //         try {
//       //           const repairedJson = jsonrepair(accumulatedChunks);
//       //           const partialData = JSON.parse(repairedJson);

//       //           if (partialData.slides) {
//       //             if (
//       //               partialData.slides.length !== previousSlidesLength.current &&
//       //               partialData.slides.length > 0
//       //             ) {
//       //               dispatch(
//       //                 setPresentationData({
//       //                   ...partialData,
//       //                   slides: partialData.slides,
//       //                 })
//       //               );
//       //               previousSlidesLength.current = partialData.slides.length;
//       //               setLoading(false);
//       //             }
//       //           }
//       //         } catch (error) {
//       //           // JSON isn't complete yet, continue accumulating
//       //           console.debug("JSON repair failed, continuing to accumulate chunks");
//       //         }
//       //         break;

//       //       case "complete":
//       //         try {
//       //           dispatch(setPresentationData(data.presentation));
//       //           dispatch(setStreaming(false));
//       //           setLoading(false);
//       //           cleanup();
                
//       //           // Remove stream parameter from URL
//       //           const newUrl = new URL(window.location.href);
//       //           newUrl.searchParams.delete("stream");
//       //           window.history.replaceState({}, "", newUrl.toString());
//       //         } catch (error) {
//       //           console.error("Error handling complete event:", error);
//       //           cleanup();
//       //           setError(true);
//       //         }
//       //         break;

//       //       case "closing":
//       //         try {
//       //           dispatch(setPresentationData(data.presentation));
//       //           setLoading(false);
//       //           dispatch(setStreaming(false));
//       //           cleanup();
                
//       //           // Remove stream parameter from URL
//       //           const newUrl = new URL(window.location.href);
//       //           newUrl.searchParams.delete("stream");
//       //           window.history.replaceState({}, "", newUrl.toString());
//       //         } catch (error) {
//       //           console.error("Error handling closing event:", error);
//       //           cleanup();
//       //           setError(true);
//       //         }
//       //         break;

//       //       default:
//       //         console.warn("Unknown event type:", data.type);
//       //     }
//       //   } catch (error) {
//       //     console.error("Error parsing event data:", error);
//       //   }
//       // });

//       // eventSourceRef.current.onerror = (error) => {
//       //   console.error("EventSource failed:", error);
//       //   cleanup();
//       eventSource = new EventSource(
//         `/api/v1/ppt/presentation/stream?presentation_id=${presentationId}`
//       );

//       eventSource.addEventListener("response", (event) => {
//         const data = JSON.parse(event.data);

//         switch (data.type) {
//           case "chunk":
//             accumulatedChunks += data.chunk;
//             try {
//               const repairedJson = jsonrepair(accumulatedChunks);
//               const partialData = JSON.parse(repairedJson);

//               if (partialData.slides) {
//                 if (
//                   partialData.slides.length !== previousSlidesLength.current &&
//                   partialData.slides.length > 0
//                 ) {
//                   dispatch(
//                     setPresentationData({
//                       ...partialData,
//                       slides: partialData.slides,
//                     })
//                   );
//                   previousSlidesLength.current = partialData.slides.length;
//                   setLoading(false);
//                 }
//               }
//             } catch (error) {
//               // JSON isn't complete yet, continue accumulating
//             }
//             break;

//           case "complete":
//             try {
//               dispatch(setPresentationData(data.presentation));
//               dispatch(setStreaming(false));
//               setLoading(false);
//               eventSource.close();

//               // Remove stream parameter from URL
//               const newUrl = new URL(window.location.href);
//               newUrl.searchParams.delete("stream");
//               window.history.replaceState({}, "", newUrl.toString());
//             } catch (error) {
//               eventSource.close();
//               console.error("Error parsing accumulated chunks:", error);
//             }
//             accumulatedChunks = "";
//             break;

//           case "closing":
//             dispatch(setPresentationData(data.presentation));
//             setLoading(false);
//             dispatch(setStreaming(false));
//             eventSource.close();

//             // Remove stream parameter from URL
//             const newUrl = new URL(window.location.href);
//             newUrl.searchParams.delete("stream");
//             window.history.replaceState({}, "", newUrl.toString());
//             break;
//           case "error":
//             eventSource.close();
//             toast.error("Error in outline streaming", {
//               description:
//                 data.detail ||
//                 "Failed to connect to the server. Please try again.",
//             });
//             setLoading(false);
//             dispatch(setStreaming(false));
//             setError(true);
//              break;
//         }
//       });

//       eventSource.onerror = (error) => {
//         console.error("EventSource failed:", error);
//         setLoading(false);
//         dispatch(setStreaming(false));
//         setError(true);
//       };
//     };

//     if (stream) {
//       initializeStream();
//     } else {
//       fetchUserSlides();
//     }

//     // Cleanup function
// //     return cleanup;
// //   }, [presentationId, stream]); // Remove problematic dependencies that cause re-renders
// // }; 
//     return () => {
//       if (eventSource) {
//         eventSource.close();
//       }
//     };
//   }, [presentationId, stream, dispatch, setLoading, setError, fetchUserSlides]);
// };

import { useEffect, useRef } from "react";
import { useDispatch } from "react-redux";
import {
  clearPresentationData,
  setPresentationData,
  setStreaming,
} from "@/store/slices/presentationGeneration";
import { jsonrepair } from "jsonrepair";
import { toast } from "sonner";
import { MixpanelEvent, trackEvent } from "@/utils/mixpanel";

export const usePresentationStreaming = (
  presentationId: string,
  stream: string | null,
  setLoading: (loading: boolean) => void,
  setError: (error: boolean) => void,
  fetchUserSlides: () => void
) => {
  const dispatch = useDispatch();
  const previousSlidesLength = useRef(0);

  useEffect(() => {
    let eventSource: EventSource;
    let accumulatedChunks = "";

    const initializeStream = async () => {
      dispatch(setStreaming(true));
      dispatch(clearPresentationData());

      trackEvent(MixpanelEvent.Presentation_Stream_API_Call);

      eventSource = new EventSource(
        `/api/v1/ppt/presentation/stream?presentation_id=${presentationId}`
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
                if (
                  partialData.slides.length !== previousSlidesLength.current &&
                  partialData.slides.length > 0
                ) {
                  dispatch(
                    setPresentationData({
                      ...partialData,
                      slides: partialData.slides,
                    })
                  );
                  previousSlidesLength.current = partialData.slides.length;
                  setLoading(false);
                }
              }
            } catch (error) {
              // JSON isn't complete yet, continue accumulating
            }
            break;

          case "complete":
            try {
              dispatch(setPresentationData(data.presentation));
              dispatch(setStreaming(false));
              setLoading(false);
              eventSource.close();

              // Remove stream parameter from URL
              const newUrl = new URL(window.location.href);
              newUrl.searchParams.delete("stream");
              window.history.replaceState({}, "", newUrl.toString());
            } catch (error) {
              eventSource.close();
              console.error("Error parsing accumulated chunks:", error);
            }
            accumulatedChunks = "";
            break;

          case "closing":
            dispatch(setPresentationData(data.presentation));
            setLoading(false);
            dispatch(setStreaming(false));
            eventSource.close();

            // Remove stream parameter from URL
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete("stream");
            window.history.replaceState({}, "", newUrl.toString());
            break;
          case "error":
            eventSource.close();
            toast.error("Error in outline streaming", {
              description:
                data.detail ||
                "Failed to connect to the server. Please try again.",
            });
            setLoading(false);
            dispatch(setStreaming(false));
            setError(true);
            break;
        }
      });

      eventSource.onerror = (error) => {
        console.error("EventSource failed:", error);
        setLoading(false);
        dispatch(setStreaming(false));
        setError(true);
        eventSource.close();
      };
    };

    if (stream) {
      initializeStream();
    } else {
      fetchUserSlides();
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
    };
  }, [presentationId, stream, dispatch, setLoading, setError, fetchUserSlides]);
};