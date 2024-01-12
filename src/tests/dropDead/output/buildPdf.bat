REM Deleting files first so we know when they fail
DEL dropDead.pdf
DEL dropDeadReport.pdf


C:\ProgramFiles\ChromiumHtmlToPdf\ChromiumHtmlToPdfConsole.exe --input dropDead.html --output dropDead.pdf
C:\ProgramFiles\ChromiumHtmlToPdf\ChromiumHtmlToPdfConsole.exe --input dropDeadReport.html --output dropDeadReport.pdf
