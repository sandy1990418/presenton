import json
import os

from api.utils.utils import get_resource

# Try to import fastembed, but handle import errors gracefully
try:
    from fastembed_vectorstore import FastembedVectorstore, FastembedEmbeddingModel
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False
    print("Warning: fastembed_vectorstore not available")


def get_icons_vectorstore():
    """
    Get icons vector store for similarity search.
    Returns None if fastembed is not available or fails to initialize.
    """
    # Temporarily disable vector store due to pyo3_runtime.PanicException
    # TODO: Fix fastembed initialization issue
    print("Vector store temporarily disabled due to fastembed initialization issues")
    return None
    
    # Original code kept for future re-enabling:
    # if not FASTEMBED_AVAILABLE:
    #     print("FastEmbed not available, returning None")
    #     return None
    # 
    # try:
    #     vector_store_path = get_resource("assets/icons_vectorstore.json")
    #     embedding_model = FastembedEmbeddingModel.BGESmallENV15
    #
    #     if os.path.exists(vector_store_path):
    #         try:
    #             return FastembedVectorstore.load(embedding_model, vector_store_path)
    #         except Exception as load_error:
    #             print(f"Error loading existing vector store: {load_error}")
    #             # If loading fails, try to create a new one
    #             try:
    #                 os.remove(vector_store_path)
    #                 print("Removed corrupted vector store file")
    #             except:
    #                 pass
    #
    #     # Create new vector store
    #     vector_store = FastembedVectorstore(embedding_model)
    #     with open(get_resource("assets/icons.json"), "r") as f:
    #         icons = json.load(f)
    #     documents = []
    #     for each in icons["icons"]:
    #         if each["name"].split("-")[-1] == "bold":
    #             documents.append(f"{each['name']}||{each['tags']}")
    #
    #     vector_store.embed_documents(documents)
    #     vector_store.save(vector_store_path)
    #
    #     return vector_store
    # except Exception as e:
    #     print(f"Error initializing vector store: {e}")
    #     print(f"Error type: {type(e).__name__}")
    #     # Handle specific pyo3_runtime.PanicException and other low-level errors
    #     return None
