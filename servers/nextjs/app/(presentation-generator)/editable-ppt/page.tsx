"use client";

import React from "react";
import EditablePPTViewer from "../components/EditablePPTViewer";

const EditablePPTPage = () => {
  const handleSave = (content: any) => {
    console.log("Saving presentation:", content);
    // You can implement actual save logic here
    // For example, send to API or save to local storage
  };

  return (
    <div className="container mx-auto py-8">
      <EditablePPTViewer 
        onSave={handleSave}
        className="w-full"
      />
    </div>
  );
};

export default EditablePPTPage;