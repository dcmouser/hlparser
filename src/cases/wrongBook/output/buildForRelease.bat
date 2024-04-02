
copy wrongBook.pdf .\WrongBookCasePack\
copy wrongBook.pdf .\WrongBookCasePackMini\


set zformat=zip
set extraoptions=
set zcmd="c:\program files\7-zip\7z" a -t%zformat% -r %extraoptions%

set fname=.\WrongBookCasePack.zip
set folder=WrongBookCasePack
DEL %fname%
echo %zcmd% $fname% %folder%
cd %folder%
%zcmd% ..\%fname% .
cd ..

set fname=.\WrongBookCasePackMini.zip
set folder=WrongBookCasePackMini
DEL %fname%
echo %zcmd% $fname% %folder%
cd %folder%
%zcmd% ..\%fname% .
cd ..

copy wrongBook.pdf E:\MyDocs\Programming\VersionControl\Git\highlow\games\v2\cases\theWrongBook