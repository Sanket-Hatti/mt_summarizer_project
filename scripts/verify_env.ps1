<#
Quick environment verification for the mt_summarizer_project.
Run after activating your virtualenv:
    . .venv\Scripts\Activate.ps1
    .\scripts\verify_env.ps1
This script prints whether required Python packages are importable and whether pdftoppm and tesseract are on PATH.
#>
Write-Output "--- Verifying Python packages and binaries ---"

# Confirm Python interpreter and venv activation
$python = (Get-Command python -ErrorAction SilentlyContinue).Path
if (-not $python) {
    Write-Output "Python not found on PATH. Activate your venv first: `. .venv\Scripts\Activate.ps1`"
} else {
    Write-Output "Python executable: $python"
}

# Run a small python snippet to check imports and shutil.which
$code = @'
import importlib, shutil, os, sys
modules = ('PyPDF2','pdf2image')
for m in modules:
    try:
        importlib.import_module(m)
        print(m + ' OK')
    except Exception as e:
        print(m + ' MISSING or error: ' + str(e))
print('pdftoppm on PATH:', shutil.which('pdftoppm') or 'not found')
print('tesseract on PATH:', shutil.which('tesseract') or 'not found')
print('TESSERACT_CMD env:', os.environ.get('TESSERACT_CMD') or '(not set)')
print('POPPLER_PATH env:', os.environ.get('POPPLER_PATH') or '(not set)')
'@

python - <<PY
$code
PY

Write-Output "--- End verification ---"