@echo off
powershell -ExecutionPolicy Bypass -File "%~dp0build_release_archive.ps1" %*
