"""
JSON Project Exporter and Importer.
"""
from app.models.project import ProjectData


class JSONExporter:
    @staticmethod
    def export_project(project: ProjectData, file_path: str) -> bool:
        project.save_to_file(file_path)
        return True

    @staticmethod
    def export_to_json(project: ProjectData, file_path: str) -> bool:
        return JSONExporter.export_project(project, file_path)

    @staticmethod
    def import_project(file_path: str) -> ProjectData:
        return ProjectData.load_from_file(file_path)

    @staticmethod
    def import_from_json(file_path: str) -> ProjectData:
        return JSONExporter.import_project(file_path)
