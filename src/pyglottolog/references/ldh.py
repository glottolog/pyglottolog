import os
from tempfile import gettempdir
import zipfile
from urllib.request import urlretrieve

URL = "http://cdstar.shh.mpg.de//bitstreams/EAEA0-A662-A618-386E-0/ldh_description.bib.zip"


def download(bibfile, log):  # pragma: no cover
    fname = 'description.bib'
    tmpdir = gettempdir()
    zipped = os.path.join(tmpdir, fname + '.zip')
    urlretrieve(URL, zipped)
    zip = zipfile.ZipFile(zipped)
    zip.extract(fname, tmpdir)
    os.remove(zipped)

    bibfile.update(os.path.join(tmpdir, fname), log=log)
    bibfile.check(log)

    os.remove(os.path.join(tmpdir, fname))
