# Versioning guide

## Current scheme
- canonical version: `pyproject.toml`
- package version mirror: `src/tunnellio/__init__.py`
- human changelog: `CHANGELOG.md`

## Version bump checklist
1. update version in `pyproject.toml`
2. update version in `src/tunnellio/__init__.py`
3. add changelog entry
4. rebuild binary
5. rebuild release archive

## Git start checklist
1. `git init`
2. verify `.gitignore`
3. `git add .`
4. `git commit -m "Initial import"`
5. later add remote and push

## Suggested branch model
Simple start:
- `main` for release-ready state
- short-lived feature branches for changes

## Suggested commit style
Use concise technical messages, for example:
- `Add Windows truststore TLS backend`
- `Add PyInstaller release scripts`
- `Document Windows binary build flow`
