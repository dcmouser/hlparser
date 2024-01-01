mkdir pdftmp
mkdir pdf

REM Deleting files first so we know when they fail
DEL pdftmp\dropDead.pdf
DEL pdf\dropDead.pdf


C:\ProgramFiles\ChromiumHtmlToPdf\ChromiumHtmlToPdfConsole.exe --input dropDead.html --output pdftmp/dropDeadTmp.pdf
"C:\Program Files\PDF24\pdf24-DocTool.exe" -applyProfile -profile "user/jrcombine" -outputFile pdf/dropDead.pdf pdftmp/dropDeadTmp.pdf
