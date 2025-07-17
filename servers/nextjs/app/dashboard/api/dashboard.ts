import {
  getHeader,
  getHeaderForFormData,
} from "@/app/(presentation-generator)/services/api/header";
import { apiClient } from "@/utils/apiClient";



export interface PresentationResponse {
  id: string;
  title: string;
  created_at: string;
  data: any | null;
  file: string;
  n_slides: number;
  prompt: string;
  summary: string | null;
    theme: string;
    titles: string[];
    user_id: string;
    vector_store: any;

    thumbnail: string;
    slide: any;
}

export class DashboardApi {

  static async getPresentations(): Promise<PresentationResponse[]> {
    try {
      const response = await apiClient.get<PresentationResponse[]>('/user_presentations');
      
      if (response.success && response.data) {
        return response.data;
      } else if (response.status === 404) {
        console.log("No presentations found");
        return [];
      }
      
      throw new Error(response.error || 'Failed to fetch presentations');
    } catch (error) {
      console.error("Error fetching presentations:", error);
      throw error;
    }
  }
  static async getPresentation(id: string) {
    try {
      const response = await apiClient.get(`/presentation?presentation_id=${id}`);
      
      if (response.success && response.data) {
        return response.data;
      }
      
      throw new Error(response.error || "Presentation not found");
    } catch (error) {
      console.error("Error fetching presentations:", error);
      throw error;
    }
  }
  static async deletePresentation(presentation_id: string) {
    try {
      const response = await fetch(
        `/api/v1/ppt/delete?presentation_id=${presentation_id}`,
        {
          method: "DELETE",
          headers: getHeader(),
        }
      );

      if (response.status === 204) {
        return true;
      }
      return false;
    } catch (error) {
      console.error("Error deleting presentation:", error);
      throw error;
    }
  }
  
}
