import os
from os import stat
from pwd import getpwuid
from glob import glob
from shutil import rmtree

def main():
    for t in glob('/tmp/tmp*'):
        st=os.stat(t)
        userinfo = getpwuid(st.st_uid).pw_name
        if userinfo=='sfleisch':
            print('{} {}'.format(t,userinfo))
            rmtree(t)

if __name__=="__main__":
    main()
