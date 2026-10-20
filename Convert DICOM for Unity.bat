@echo off
rem Opens the converter window: DICOM / NRRD -> volume for the viewer (backend\out\latest.txt).
start "" "%~dp0backend\.venv\Scripts\pythonw.exe" "%~dp0backend\tools\dicom_converter_app.py"
