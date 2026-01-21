import os

from fastapi.responses import FileResponse


def media_type_for_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".pptx":
        return (
            "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        )
    return "application/octet-stream"


def resolve_file_metadata(file_path: str) -> tuple[str, str]:
    filename = os.path.basename(file_path)
    media_type = media_type_for_file(file_path)
    return filename, media_type


def build_file_response(file_path: str) -> FileResponse:
    filename, media_type = resolve_file_metadata(file_path)
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
    )
