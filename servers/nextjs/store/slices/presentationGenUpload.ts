import { PresentationConfig } from "@/app/(presentation-generator)/upload/type";
import { createSlice, PayloadAction } from "@reduxjs/toolkit";

interface PresentationGenUploadState {
  config: PresentationConfig | null;
  files: any;
  webSearchEnabled: boolean;
}

const initialState: PresentationGenUploadState = {
  config: null,
  files: [],
  webSearchEnabled: false,
};

export const presentationGenUploadSlice = createSlice({
  name: "pptGenUpload",
  initialState,
  reducers: {
    setPptGenUploadState: (
      state,
      action: PayloadAction<Partial<PresentationGenUploadState>>
    ) => {
      const payload = action.payload;
      if (payload.config !== undefined) state.config = payload.config;
      if (payload.files !== undefined) state.files = payload.files;
      if (payload.webSearchEnabled !== undefined) state.webSearchEnabled = payload.webSearchEnabled;
    },
   
  },
});

export const { setPptGenUploadState, } =
  presentationGenUploadSlice.actions;
export default presentationGenUploadSlice.reducer;
