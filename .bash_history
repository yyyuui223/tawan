ls
find . -maxdepth 1 ! -name 'mydiary' ! -name 'mato_exe' ! -name '.' -exec rm -rf {} +
ls
exit
